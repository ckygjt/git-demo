"""联网检索适配器：文献/数据溯源 与 传播异常核验。

real：Tavily HTTP API（httpx 直连）
mock：读取 config/mock_sources.yaml 的 references / spread
"""

from __future__ import annotations

import logging

from ..config import mock_sources, settings
from ..schemas import EvidenceStatus
from .base import CheckOutcome, CheckRequest, unverifiable

try:
    import httpx
except Exception:  # noqa: BLE001
    httpx = None  # type: ignore[assignment]

log = logging.getLogger(__name__)
TAVILY_URL = "https://api.tavily.com/search"

BATCH_COPY_THRESHOLD = 5  # 同图同话术命中数 ≥ 此值视为 GEO 水军式批量复制


def tavily(query: str, max_results: int = 5) -> list[dict] | None:
    """返回检索结果列表；失败或无 Key 返回 None（调用方降级为不可验）。"""
    s = settings()
    if httpx is None or not s.tavily_api_key:
        return None
    try:
        r = httpx.post(TAVILY_URL, json={
            "api_key": s.tavily_api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
        }, timeout=s.timeout)
        r.raise_for_status()
        return (r.json() or {}).get("results", []) or []
    except Exception as e:  # noqa: BLE001
        log.warning("tavily 检索失败：%s", type(e).__name__)
        return None


def check_reference(req: CheckRequest) -> CheckOutcome:
    """文献/数据/机构线索的检索核验。"""
    src = mock_sources()
    if settings().mock:
        refs = src.get("references") or []
        hit = next((r for r in refs if r and (r in req.value or req.value in r)), None)
        if hit:
            return CheckOutcome(EvidenceStatus.CONFIRMED, f"本地信源库命中：{hit}", confidence=0.7)
        return CheckOutcome(EvidenceStatus.NOT_FOUND, f"本地信源库未检索到「{req.value}」",
                            confidence=0.5, needs_human_review=True)

    results = tavily(req.value)
    if results is None:
        return unverifiable("检索工具不可用（未配置 Key 或调用失败）")
    if results:
        top = results[0]
        return CheckOutcome(EvidenceStatus.CONFIRMED, f"检索命中 {len(results)} 条：{top.get('title', '')[:60]}",
                            source_url=top.get("url"), confidence=0.6, needs_human_review=True,
                            data={"count": len(results)})
    return CheckOutcome(EvidenceStatus.NOT_FOUND, f"未检索到「{req.value}」",
                        confidence=0.5, needs_human_review=True)


def check_spread(req: CheckRequest) -> CheckOutcome:
    """传播异常核验：同图同话术是否多平台批量复制。"""
    src = mock_sources()
    if settings().mock:
        info = (src.get("spread") or {}).get(req.value)
        if not info:
            return CheckOutcome(EvidenceStatus.NOT_FOUND, f"未见「{req.value}」的批量传播记录", confidence=0.5)
        copies = int(info.get("copies", 0))
        platforms = info.get("platforms") or []
        if copies >= BATCH_COPY_THRESHOLD:
            return CheckOutcome(EvidenceStatus.CONFIRMED,
                                f"发现 {copies} 处近似内容，分布于 {'、'.join(platforms)}（GEO 水军特征）",
                                confidence=0.7, needs_human_review=True, data={"copies": copies})
        return CheckOutcome(EvidenceStatus.NOT_FOUND, f"仅 {copies} 处近似内容，未构成批量复制", confidence=0.5)

    results = tavily(f"{req.value} {req.extra.get('snippet', '')}".strip(), max_results=8)
    if results is None:
        return unverifiable("检索工具不可用，传播异常未核验")
    if len(results) >= BATCH_COPY_THRESHOLD:
        return CheckOutcome(EvidenceStatus.CONFIRMED,
                            f"检索到 {len(results)} 处高度近似内容（GEO 水军特征）",
                            source_url=results[0].get("url"), confidence=0.6,
                            needs_human_review=True, data={"copies": len(results)})
    return CheckOutcome(EvidenceStatus.NOT_FOUND, f"仅 {len(results)} 处近似内容，未构成批量复制", confidence=0.5)
