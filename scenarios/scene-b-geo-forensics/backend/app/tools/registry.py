"""工具注册表：按 kind 分发、并行执行、缓存、统一降级。

任何工具抛异常或超时，都降级为 UNVERIFIABLE（needs_human_review=True），
绝不把"查不到 / 调不通"当成"伪造"。
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from ..config import settings, thresholds
from ..fusion import rules
from ..schemas import (
    Evidence,
    EvidenceStatus,
    POLARITY_CN,
    STATUS_CN,
)
from . import institution, nmpa, search
from .base import CheckOutcome, CheckRequest, unverifiable

DISPATCH: dict[str, tuple[str, object]] = {
    "filing": ("备案库核验", nmpa.check_filing),
    "cert": ("证书核验", institution.check_cert),
    "institution": ("机构核验", institution.check_institution),
    "expert": ("专家核验", institution.check_expert),
    "reference": ("检索核验", search.check_reference),
    "spread": ("传播核验", search.check_spread),
}

# (kind, status) → thresholds.weights 的键
WEIGHT_KEY: dict[tuple[str, EvidenceStatus], str] = {
    ("filing", EvidenceStatus.CONFIRMED): "filing_confirmed",
    ("filing", EvidenceStatus.CONTRADICTED): "filing_subject_mismatch",
    ("filing", EvidenceStatus.NOT_FOUND): "filing_not_found",
    ("cert", EvidenceStatus.CONFIRMED): "cert_confirmed",
    ("cert", EvidenceStatus.CONTRADICTED): "cert_subject_mismatch",
    ("cert", EvidenceStatus.NOT_FOUND): "cert_not_found",
    ("institution", EvidenceStatus.CONFIRMED): "institution_confirmed",
    ("institution", EvidenceStatus.CONTRADICTED): "institution_contradicted",
    ("institution", EvidenceStatus.NOT_FOUND): "institution_not_found",
    ("expert", EvidenceStatus.CONFIRMED): "expert_confirmed",
    ("expert", EvidenceStatus.CONTRADICTED): "expert_contradicted",
    ("expert", EvidenceStatus.NOT_FOUND): "expert_not_found",
    ("reference", EvidenceStatus.CONFIRMED): "reference_found",
    ("reference", EvidenceStatus.NOT_FOUND): "reference_missing",
    ("spread", EvidenceStatus.CONFIRMED): "spread_batch",
    ("spread", EvidenceStatus.NOT_FOUND): "spread_clean",
}

_CACHE: dict[tuple, tuple[CheckOutcome, int]] = {}
# 最近一次核验的原始数据（如备案核定范围、证书有效期），供一致性判定复用，避免重复调用
LAST_DATA: dict[tuple[str, str], dict] = {}
MAX_WORKERS = 4


def get_data(kind: str, value: str) -> dict:
    return LAST_DATA.get((kind, value), {})


def _run_one(req: CheckRequest) -> tuple[CheckRequest, CheckOutcome, int]:
    key = (req.kind, req.value, req.brand, req.org)
    if settings().cache and key in _CACHE:
        outcome, ms = _CACHE[key]
        return req, outcome, ms

    entry = DISPATCH.get(req.kind)
    if entry is None:
        return req, unverifiable(f"未支持的核验类型：{req.kind}"), 0

    fn = entry[1]
    t0 = time.perf_counter()
    try:
        outcome = fn(req)  # type: ignore[operator]
    except Exception as e:  # noqa: BLE001
        outcome = unverifiable(f"{type(e).__name__}: {e}")
    ms = int((time.perf_counter() - t0) * 1000)

    if outcome.data:
        LAST_DATA[(req.kind, req.value)] = outcome.data

    if settings().cache:
        _CACHE[key] = (outcome, ms)
    return req, outcome, ms


def to_evidence(req: CheckRequest, outcome: CheckOutcome, elapsed_ms: int, thr: dict) -> Evidence:
    weight_key = WEIGHT_KEY.get((req.kind, outcome.status), "")
    ev = rules.make_evidence(
        tool=req.kind,
        tool_cn=DISPATCH.get(req.kind, (req.kind,))[0],
        kind=req.kind,
        query=req.value,
        status=outcome.status,
        summary=outcome.summary,
        weight_key=weight_key,
        thr=thr,
        source_url=outcome.source_url,
        degraded=outcome.degraded,
        needs_human_review=outcome.needs_human_review,
        elapsed_ms=elapsed_ms,
    )
    ev.status_cn = STATUS_CN.get(outcome.status, outcome.status.value)
    ev.polarity_cn = POLARITY_CN.get(ev.polarity, "")
    return ev


def run_checks(reqs: list[CheckRequest], thr: dict | None = None) -> list[Evidence]:
    if not reqs:
        return []
    thr = thr or thresholds()
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(reqs))) as ex:
        results = list(ex.map(_run_one, reqs))
    return [to_evidence(req, outcome, ms, thr) for req, outcome, ms in results]


def clear_cache() -> None:
    _CACHE.clear()
