"""机构资质 / 证书 / 专家身份核验适配器。

real：检索核验（结果一律标记需人工复核，因为检索命中不等于官方确认）
mock：读取 config/mock_sources.yaml 的 certs / institutions / institution_blacklist / experts
"""

from __future__ import annotations

from ..config import mock_sources, settings
from ..schemas import EvidenceStatus
from .base import CheckOutcome, CheckRequest, unverifiable
from .search import tavily


def check_cert(req: CheckRequest) -> CheckOutcome:
    no = (req.value or "").strip()
    if not no:
        return unverifiable("未提供证书编号")

    if settings().mock:
        cert = (mock_sources().get("certs") or {}).get(no)
        if not cert:
            return CheckOutcome(EvidenceStatus.NOT_FOUND, f"本地证书库未收录编号 {no}",
                                confidence=0.5, needs_human_review=True)
        brand = (req.brand or "").strip()
        subject = cert.get("subject", "")
        if brand and subject and brand not in subject:
            return CheckOutcome(
                EvidenceStatus.CONTRADICTED,
                f"证书 {no} 获证主体为「{subject}」，与宣称品牌「{brand}」不一致",
                confidence=0.85, needs_human_review=True, data=cert)
        return CheckOutcome(
            EvidenceStatus.CONFIRMED,
            f"证书 {no} 已收录：发证机构 {cert.get('issuer', '')}，有效期至 {cert.get('valid_until', '')}",
            confidence=0.8, data=cert)

    results = tavily(f'"{no}" 检测报告 证书 资质')
    if results is None:
        return unverifiable("检索工具不可用，证书编号未核验")
    if results:
        return CheckOutcome(EvidenceStatus.CONFIRMED, f"检索命中证书编号 {no} 的 {len(results)} 条线索",
                            source_url=results[0].get("url"), confidence=0.5,
                            needs_human_review=True, data={"count": len(results)})
    return CheckOutcome(EvidenceStatus.NOT_FOUND, f"未检索到证书编号 {no}",
                        confidence=0.5, needs_human_review=True)


def check_institution(req: CheckRequest) -> CheckOutcome:
    name = (req.value or "").strip()
    if not name:
        return unverifiable("未提供机构名称")

    if settings().mock:
        src = mock_sources()
        if name in (src.get("institution_blacklist") or []):
            return CheckOutcome(EvidenceStatus.CONTRADICTED,
                                f"机构「{name}」在虚构机构名单中，无有效资质登记",
                                confidence=0.8, needs_human_review=True)
        if name in (src.get("institutions") or []):
            return CheckOutcome(EvidenceStatus.CONFIRMED, f"机构「{name}」在资质库内", confidence=0.8)
        return CheckOutcome(EvidenceStatus.NOT_FOUND, f"资质库未收录机构「{name}」",
                            confidence=0.5, needs_human_review=True)

    results = tavily(f"{name} 资质 CMA CNAS 认证")
    if results is None:
        return unverifiable("检索工具不可用，机构资质未核验")
    if results:
        return CheckOutcome(EvidenceStatus.CONFIRMED, f"检索到机构「{name}」的 {len(results)} 条资质线索",
                            source_url=results[0].get("url"), confidence=0.5,
                            needs_human_review=True, data={"count": len(results)})
    return CheckOutcome(EvidenceStatus.NOT_FOUND, f"未检索到机构「{name}」的资质信息",
                        confidence=0.5, needs_human_review=True)


# 泛称机构：不具备比对价值，拿它做任职单位比对会制造误判
GENERIC_ORGS = ("三甲医院", "权威机构", "知名医院", "公立医院", "大型医院", "专业机构", "权威检测")


def check_expert(req: CheckRequest) -> CheckOutcome:
    name = (req.value or "").strip()
    if not name:
        return unverifiable("未提供专家姓名")
    if req.org in GENERIC_ORGS:
        req = CheckRequest(kind=req.kind, value=req.value, brand=req.brand, org="", extra=req.extra)

    if settings().mock:
        src = mock_sources()
        target_org = (req.org or "").strip()
        pool = src.get("experts") or []
        matched = [e for e in pool if e.get("name") == name]
        if matched:
            e = matched[0]
            if target_org and e.get("hospital") and target_org not in e["hospital"]:
                return CheckOutcome(
                    EvidenceStatus.CONTRADICTED,
                    f"专家「{name}」登记任职于「{e['hospital']}」，与宣称机构「{target_org}」不一致",
                    confidence=0.8, needs_human_review=True, data=e)
            return CheckOutcome(EvidenceStatus.CONFIRMED,
                                f"专家「{name}」核验通过：{e.get('hospital', '')} {e.get('title', '')}",
                                confidence=0.75, data=e)
        return CheckOutcome(EvidenceStatus.NOT_FOUND, f"专家库未收录「{name}」",
                            confidence=0.5, needs_human_review=True)

    query = f"{name} {req.org or ''} 皮肤科 任职".strip()
    results = tavily(query)
    if results is None:
        return unverifiable("检索工具不可用，专家身份未核验")
    if results:
        return CheckOutcome(EvidenceStatus.CONFIRMED, f"检索到「{name}」的 {len(results)} 条公开线索",
                            source_url=results[0].get("url"), confidence=0.5,
                            needs_human_review=True, data={"count": len(results)})
    return CheckOutcome(EvidenceStatus.NOT_FOUND, f"未检索到专家「{name}」的公开任职信息",
                        confidence=0.5, needs_human_review=True)
