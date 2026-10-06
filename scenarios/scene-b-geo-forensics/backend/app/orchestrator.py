"""场景B 编排器：S0 受理 → S1 要素抽取 → S2 取证（占位） → S3 并行信源核验
→ S4 一致性与合规 → S5 证据融合 → S6 处置与报告。

约定：yield ("event", StepEvent) ... 最后 yield ("result", VerifyResult)
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Iterator

from .config import settings, thresholds
from .schemas import (
    CaseInput,
    Claim,
    Evidence,
    EvidenceStatus,
    Finding,
    POLARITY_CN,
    STATUS_CN,
    StepEvent,
    VerifyResult,
)
from .fusion import disposition, rules
from .repo import save_case
from .tools import CheckRequest, run_checks
from .tools import llm
from .tools.registry import DISPATCH, get_data

MAX_CHECKS = 12


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


def _uniq(items) -> list[str]:
    return [x for x in dict.fromkeys([i for i in items if i])]


def verify(inp: CaseInput, case_id: str) -> Iterator[tuple[str, object]]:
    t_start = time.perf_counter()
    thr = thresholds()
    s = settings()
    mode = s.effective
    text = re.sub(r"\s+", " ", inp.text or "").strip()

    evidences: list[Evidence] = []
    findings: list[Finding] = []

    # ---------- S0 受理 ----------
    t0 = time.perf_counter()
    yield "event", StepEvent(step="s0", title="S0 受理", status="running")
    usable_imgs = [a for a in inp.images if a.usable and a.path and Path(a.path).exists()]
    yield "event", StepEvent(
        step="s0", title="S0 受理", status="done", elapsed_ms=_ms(t0),
        detail=f"{len(inp.images)} 张图片（{len(usable_imgs)} 张可读）；文案 {len(text)} 字；来源 {inp.source_url or '未填写'}",
        data={"images": [a.model_dump(mode="json") for a in inp.images]},
    )

    # ---------- S1 要素抽取 ----------
    t0 = time.perf_counter()
    yield "event", StepEvent(step="s1", title="S1 要素抽取", status="running")

    vision_fields: list[dict] = []
    for a in [x for x in inp.images if x.usable]:
        try:
            if a.path and Path(a.path).exists():
                data = Path(a.path).read_bytes()
                fields = llm.vision_extract(data, a.name, a.mime or "image/jpeg")
            else:  # 示例素材：无本地文件，按名称回放
                fields = llm.vision_extract(b"", a.name)
            fields["_image"] = a.name
            vision_fields.append(fields)
        except Exception as e:  # noqa: BLE001
            vision_fields.append({"_image": a.name, "_error": f"{type(e).__name__}: {e}"})

    numbers = rules.extract_numbers(text)
    llm_entities = llm.text_extract(text) or {}

    cert_nos = _uniq(list(numbers["cert_no"]) + [f.get("cert_no") for f in vision_fields]
                     + list(llm_entities.get("cert_no") or []))
    filing_nos = _uniq(list(numbers["filing_no"]) + [f.get("filing_no") for f in vision_fields]
                       + list(llm_entities.get("filing_no") or []))
    orgs = _uniq(list(numbers["orgs"]) + [f.get("issuer") or f.get("org") for f in vision_fields]
                 + list(llm_entities.get("orgs") or []))
    persons = _uniq(list(numbers["persons"]) + [f.get("person") for f in vision_fields]
                    + list(llm_entities.get("persons") or []))

    claims: list[Claim] = rules.extract_claims(text, thr)
    if not claims and (cert_nos or filing_nos):
        claims.append(Claim(type="endorsement", type_cn="背书主张", text="图片中的证书/备案信息", entities=cert_nos + filing_nos))

    yield "event", StepEvent(
        step="s1", title="S1 要素抽取", status="done", elapsed_ms=_ms(t0),
        detail=f"主张 {len(claims)} 条；证书号 {len(cert_nos)} 个；备案号 {len(filing_nos)} 个；机构 {len(orgs)} 个；专家 {len(persons)} 人",
        data={"claims": [c.model_dump(mode="json") for c in claims],
              "cert_no": cert_nos, "filing_no": filing_nos, "orgs": orgs, "persons": persons,
              "vision": vision_fields},
    )

    # ---------- S2 技术取证（本期占位） ----------
    t0 = time.perf_counter()
    yield "event", StepEvent(
        step="s2", title="S2 技术取证", status="done", elapsed_ms=_ms(t0),
        detail="本期未启用图像取证算法，节点与权重槽位已保留，后续可接入 ELA/EXIF/AI 生成痕迹检测",
        data={"signals": []},
    )

    # ---------- S3 信源交叉核验（并行） ----------
    t0 = time.perf_counter()
    yield "event", StepEvent(step="s3", title="S3 信源交叉核验", status="running")

    brand = (inp.brand or "").strip()
    reqs: list[CheckRequest] = []
    for no in filing_nos:
        reqs.append(CheckRequest(kind="filing", value=no, brand=brand))
    for no in cert_nos:
        reqs.append(CheckRequest(kind="cert", value=no, brand=brand))
    for org in orgs:
        reqs.append(CheckRequest(kind="institution", value=org))
    # 专家所属机构优先取医疗机构，避免拿发证机构去比对任职单位
    hospital = next((o for o in orgs if "医院" in o), "")
    for person in persons:
        reqs.append(CheckRequest(kind="expert", value=person, org=hospital))

    data_claims = [c for c in claims if c.type == "data"]
    if data_claims:
        reqs.append(CheckRequest(kind="reference", value=f"{inp.product} {data_claims[0].text}".strip()))
    if inp.product or inp.brand:
        reqs.append(CheckRequest(kind="spread", value=(inp.product or inp.brand),
                                 extra={"snippet": text[:60]}))
    reqs = reqs[:MAX_CHECKS]

    evidences.extend(run_checks(reqs, thr))
    for ev in evidences:
        yield "event", StepEvent(
            step=f"tool_{ev.kind}", title=f"{ev.tool_cn} · {ev.query[:24]}", status="done",
            elapsed_ms=ev.elapsed_ms,
            detail=f"[{ev.status_cn}/{ev.polarity_cn}{ev.weight:+.0f}] {ev.summary}",
            data={"evidence": ev.model_dump(mode="json")},
        )

    degraded = sum(1 for e in evidences if e.degraded)
    yield "event", StepEvent(
        step="s3", title="S3 信源交叉核验", status="done", elapsed_ms=_ms(t0),
        detail=f"{len(evidences)} 条证据（降信 {sum(1 for e in evidences if e.polarity.value == 'down')}，"
               f"增信 {sum(1 for e in evidences if e.polarity.value == 'up')}，降级 {degraded}）",
        data={"tools": sorted({DISPATCH.get(r.kind, (r.kind,))[0] for r in reqs})},
    )

    # ---------- S4 一致性与合规判定 ----------
    t0 = time.perf_counter()
    yield "event", StepEvent(step="s4", title="S4 一致性与合规", status="running")

    scopes: list[str] = []
    categories: list[str] = []
    for ev in evidences:
        if ev.status == EvidenceStatus.CONTRADICTED and ev.kind in ("cert", "filing"):
            findings.append(Finding(dimension="主体一致", ok=False, severity="high", detail=ev.summary))
        if ev.status == EvidenceStatus.CONFIRMED and ev.kind in ("cert", "filing"):
            d = get_data(ev.kind, ev.query)
            scopes.extend(d.get("scope") or [])
            if d.get("category"):
                categories.append(d["category"])
            if d.get("subject") and brand and brand not in str(d["subject"]):
                findings.append(Finding(dimension="主体一致", ok=False, severity="high",
                                        detail=f"获证主体「{d['subject']}」与宣称品牌「{brand}」不一致"))

    for f in vision_fields:
        valid_until = f.get("valid_until") or get_data("cert", f.get("cert_no", "")).get("valid_until")
        ev = rules.check_validity(valid_until, thr) if valid_until else None
        if ev:
            evidences.append(ev)
            findings.append(Finding(dimension="时间一致", ok=False, severity="medium", detail=ev.summary))

    evidences.extend(rules.check_medical(claims, thr))
    abs_findings, abs_evidences = rules.check_absolute(claims, thr)
    findings.extend(abs_findings)
    evidences.extend(abs_evidences)

    scope_findings, scope_evidences = rules.check_scope(claims, scopes, categories, thr)
    findings.extend(scope_findings)
    evidences.extend(scope_evidences)

    for ev in evidences:
        ev.status_cn = STATUS_CN.get(ev.status, ev.status.value)
        ev.polarity_cn = POLARITY_CN.get(ev.polarity, "")

    if not scopes and (filing_nos or cert_nos):
        findings.append(Finding(dimension="语义一致", ok=True, severity="low",
                                detail="未取得备案/证书核定范围，超范围宣称待人工确认"))

    yield "event", StepEvent(
        step="s4", title="S4 一致性与合规", status="done", elapsed_ms=_ms(t0),
        detail=f"{len(findings)} 条判定（高危 {sum(1 for f in findings if f.severity == 'high' and not f.ok)} 条）",
        data={"findings": [f.model_dump(mode="json") for f in findings]},
    )

    # ---------- S5 证据融合评分 ----------
    t0 = time.perf_counter()
    verdict = rules.fuse(evidences, findings, thr)
    yield "event", StepEvent(
        step="s5", title="S5 证据融合评分", status="done", elapsed_ms=_ms(t0),
        detail=f"{verdict.level_cn}（风险分 {verdict.risk_score}，置信度 {verdict.confidence}）：{verdict.reason}",
        data={"verdict": verdict.model_dump(mode="json")},
    )

    # ---------- S6 处置与报告 ----------
    t0 = time.perf_counter()
    action = disposition.ACTION_OF[verdict.level]
    asks = disposition.supplement_requests(evidences)
    script = disposition.script(action, asks, verdict.fired_redline)
    plan = [f"{DISPATCH.get(r.kind, (r.kind,))[0]}：{r.value}" for r in reqs]

    result = VerifyResult(
        case_id=case_id, input=inp, mode=mode, claims=claims, evidences=evidences,
        findings=findings, verdict=verdict, missing_materials=asks, action=action,
        action_cn=disposition.ACTION_CN[action], script=script, plan=plan,
        cost={"provider": "dashscope" if mode == "real" else "mock", "checks": len(reqs)},
        elapsed_ms=_ms(t_start),
    )
    save_case(result)
    yield "event", StepEvent(
        step="s6", title="S6 分级处置与报告", status="done", elapsed_ms=_ms(t0),
        detail=disposition.ACTION_CN[action],
        data={"action": action, "missing_materials": asks},
    )
    yield "result", result
