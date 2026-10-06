"""证据融合与裁决：纯函数，改阈值只动 yaml。"""

from __future__ import annotations

import re
from datetime import date

from ..schemas import (
    Claim,
    Evidence,
    EvidenceStatus,
    Finding,
    Polarity,
    Verdict,
    VerdictLevel,
    VERDICT_CN,
    now_iso,
)

CLAIM_TYPE_CN = {
    "efficacy": "功效主张",
    "data": "数据主张",
    "endorsement": "背书主张",
    "ranking": "排名/绝对化主张",
    "medical": "禁用医疗用语",
}

REDLINE_CN = {
    "cert": "证书编号对应主体与宣称品牌不一致",
    "filing": "备案号对应主体与宣称品牌不一致",
    "institution": "发证机构在资质库中确认不存在",
    "expert": "专家身份与宣称机构冲突",
    "medical": "核心功效宣称使用禁用医疗用语",
}

_PAT_FILING = re.compile(r"(国妆网?[备特]字\d{6,12}|[粤沪京浙苏]G妆网备字\d{10,})")
_PAT_CERT = re.compile(r"\b([A-Z]{2,4}[-–]?\d{4}[-–]?[A-Z]{1,3}[-–]?\d{3,6})\b")
_PAT_DATA = re.compile(r"(\d+(?:\.\d+)?%|\d+(?:\.\d+)?\s*(?:倍|万人|例|人))")

# 机构名：后缀锚定 + 向前回溯，遇边界字即停，避免把前文整段吞进来
ORG_SUFFIX = ("协会", "研究院", "研究所", "学会", "医院", "检测", "认证", "集团", "有限公司", "检验站", "中心")
ORG_BACKSTOP = set("经由的和与在为是，、（）：及其等并有限公司心站会团场店组队 .；;")
ORG_NOISE = ("权威", "官方", "专业", "国际", "第三方", "国家")

# 人名：头衔前 2–3 字，过滤掉明显不是姓名的词
PERSON_TITLES = ("主任", "医师", "医生", "博士", "研究员", "教授", "专家")
PERSON_BAD_CHARS = set("科院部室会组队店场站司心经的")
PERSON_BAD_PREFIX = ("首席", "副", "总", "该", "本", "其", "某", "资深", "知名")
# 头衔在人名之后时（如「皮肤科主任陈知微」），向后取词需排除这些非人名常用词
PERSON_BAD_WORDS = {"推荐", "表示", "指出", "认为", "亲测", "力荐", "测评", "分享", "建议", "体验", "同款", "联合"}


def _is_cn(s: str) -> bool:
    return len(s) >= 2 and all("\u4e00" <= c <= "\u9fff" for c in s)


def _backward(text: str, end: int, maxlen: int = 8) -> int:
    start = end
    while start > 0 and (end - start) < maxlen:
        if text[start - 1] in ORG_BACKSTOP:
            break
        start -= 1
    return start


def extract_orgs(text: str) -> list[str]:
    if not text:
        return []
    out: list[str] = []
    for suf in ORG_SUFFIX:
        pos = text.find(suf)
        while pos != -1:
            start = _backward(text, pos)
            cand = text[start:pos + len(suf)].strip()
            if len(cand) - len(suf) >= 2 and _is_cn(cand) and not any(n in cand for n in ORG_NOISE):
                out.append(cand)
            pos = text.find(suf, pos + len(suf))
    return [x for x in dict.fromkeys(out)]


def extract_persons(text: str) -> list[str]:
    if not text:
        return []
    out: list[str] = []
    for title in PERSON_TITLES:
        pos = text.find(title)
        while pos != -1:
            cand = text[max(0, pos - 3):pos]
            for n in (3, 2):
                if len(cand) < n:
                    continue
                name = cand[-n:]
                if (_is_cn(name)
                        and not (set(name) & PERSON_BAD_CHARS)
                        and not name.startswith(PERSON_BAD_PREFIX)):
                    out.append(name)
                    break
            # 头衔在人名之前：如「皮肤科主任陈知微」
            m = re.match(r"([\u4e00-\u9fa5]{2,3})", text[pos + len(title):])
            if m:
                name = m.group(1)
                if (name not in PERSON_BAD_WORDS and _is_cn(name)
                        and not (set(name) & PERSON_BAD_CHARS)
                        and not name.startswith(PERSON_BAD_PREFIX)):
                    out.append(name)
            pos = text.find(title, pos + len(title))
    return [x for x in dict.fromkeys(out)]


def _has_any(text: str, words) -> list[str]:
    return [w for w in words if w and w in text]


def extract_claims(text: str, thr: dict) -> list[Claim]:
    """规则抽取主张；real 模式下由 LLM 结果合并补充。"""
    if not text:
        return []
    cfg = thr.get("claims", {})
    claims: list[Claim] = []

    medical = _has_any(text, cfg.get("medical_terms", []))
    if medical:
        claims.append(Claim(type="medical", type_cn=CLAIM_TYPE_CN["medical"],
                            text="／".join(medical), entities=medical))

    efficacy_hits: list[str] = []
    for scope, words in (cfg.get("efficacy_terms") or {}).items():
        hits = _has_any(text, words)
        if hits:
            efficacy_hits.extend(hits)
            claims.append(Claim(type="efficacy", type_cn=CLAIM_TYPE_CN["efficacy"],
                                text="／".join(hits), entities=[scope]))
    if efficacy_hits:
        pass

    data_hits = _PAT_DATA.findall(text)
    if data_hits:
        claims.append(Claim(type="data", type_cn=CLAIM_TYPE_CN["data"],
                            text="、".join(data_hits[:5]), entities=data_hits[:5]))

    orgs = extract_orgs(text)
    persons = extract_persons(text)
    if orgs or persons:
        claims.append(Claim(type="endorsement", type_cn=CLAIM_TYPE_CN["endorsement"],
                            text=text[:80], entities=(orgs + persons)[:8]))

    absolute = _has_any(text, cfg.get("absolute_terms", []))
    if absolute:
        claims.append(Claim(type="ranking", type_cn=CLAIM_TYPE_CN["ranking"],
                            text="／".join(absolute), entities=absolute))

    return claims


def extract_numbers(text: str) -> dict[str, list[str]]:
    return {
        "filing_no": list(dict.fromkeys(_PAT_FILING.findall(text or ""))),
        "cert_no": list(dict.fromkeys(_PAT_CERT.findall(text or ""))),
        "orgs": extract_orgs(text),
        "persons": extract_persons(text),
    }


def check_absolute(claims: list[Claim], thr: dict) -> tuple[list[Finding], list[Evidence]]:
    """绝对化 / 夸大用语：违规宣称，降信但不构成红线。"""
    findings: list[Finding] = []
    evidences: list[Evidence] = []
    for c in claims:
        if c.type != "ranking":
            continue
        findings.append(Finding(
            dimension="宣称合规", ok=False, severity="medium",
            detail=f"使用绝对化/夸大用语：{'、'.join(c.entities)}，建议改为可验证表述",
        ))
        evidences.append(make_evidence(
            tool="compliance", tool_cn="合规判定", kind="absolute", query="／".join(c.entities),
            status=EvidenceStatus.CONFIRMED,
            summary=f"绝对化/夸大用语：{'、'.join(c.entities)}",
            weight_key="absolute_term", thr=thr,
        ))
    return findings, evidences


def make_evidence(*, tool: str, tool_cn: str, kind: str, query: str, status: EvidenceStatus,
                  summary: str, weight_key: str, thr: dict, source_url: str | None = None,
                  confidence: float = 0.6, degraded: bool = False,
                  needs_human_review: bool = False, elapsed_ms: int = 0) -> Evidence:
    w = float(thr.get("weights", {}).get(weight_key, 0.0))
    polarity = Polarity.UP if w > 0 else (Polarity.DOWN if w < 0 else Polarity.NOTE)
    return Evidence(
        tool=tool, tool_cn=tool_cn, kind=kind, query=query, status=status,
        polarity=polarity, weight=w, summary=summary, source_url=source_url,
        captured_at=now_iso(), degraded=degraded, needs_human_review=needs_human_review,
        elapsed_ms=elapsed_ms,
    )


def check_medical(claims: list[Claim], thr: dict) -> list[Evidence]:
    """核心功效宣称出现禁用医疗用语 → 红线级降信证据。"""
    out = []
    for c in claims:
        if c.type != "medical":
            continue
        out.append(make_evidence(
            tool="compliance", tool_cn="合规判定", kind="medical", query="／".join(c.entities),
            status=EvidenceStatus.CONFIRMED, summary=f"宣称中使用禁用医疗用语：{'、'.join(c.entities)}",
            weight_key="medical_term", thr=thr, needs_human_review=True,
        ))
    return out


def check_scope(claims: list[Claim], known_scopes: list[str], known_categories: list[str],
                thr: dict) -> tuple[list[Finding], list[Evidence]]:
    """宣称功效 vs 备案/证书核定范围：超范围宣称与特殊功效无依据。"""
    findings: list[Finding] = []
    evidences: list[Evidence] = []
    if not known_scopes:
        return findings, evidences

    special = (thr.get("claims", {}) or {}).get("special_efficacy", [])
    claimed = {e for c in claims if c.type == "efficacy" for e in c.entities}
    allowed = set(known_scopes)
    exceeded = sorted(claimed - allowed)

    if exceeded:
        findings.append(Finding(
            dimension="语义一致", ok=False, severity="high",
            detail=f"宣称功效（{'、'.join(exceeded)}）超出备案/证书核定范围（{'、'.join(sorted(allowed))}）",
        ))
        evidences.append(make_evidence(
            tool="compliance", tool_cn="合规判定", kind="scope", query="／".join(exceeded),
            status=EvidenceStatus.CONTRADICTED, summary=f"超范围宣称：{'、'.join(exceeded)}",
            weight_key="scope_exceeded", thr=thr, needs_human_review=True,
        ))

    need_special = sorted(set(exceeded) & set(special))
    if need_special and not any("特殊" in c for c in known_categories):
        findings.append(Finding(
            dimension="法规合规", ok=False, severity="high",
            detail=f"涉及特殊功效（{'、'.join(need_special)}），未见特殊化妆品注册依据",
        ))
        evidences.append(make_evidence(
            tool="compliance", tool_cn="合规判定", kind="special", query="／".join(need_special),
            status=EvidenceStatus.NOT_FOUND, summary=f"特殊功效无注册/评价依据：{'、'.join(need_special)}",
            weight_key="special_claim_no_basis", thr=thr, needs_human_review=True,
        ))
    return findings, evidences


def check_validity(cert_valid_until: str | None, thr: dict) -> Evidence | None:
    if not cert_valid_until:
        return None
    try:
        y, m, d = (int(x) for x in cert_valid_until.split("-"))
        expired = date.today() > date(y, m, d)
    except Exception:  # noqa: BLE001
        return None
    if not expired:
        return None
    return make_evidence(
        tool="cert", tool_cn="证书核验", kind="cert_validity", query=cert_valid_until,
        status=EvidenceStatus.CONTRADICTED, summary=f"证书已过期（有效期至 {cert_valid_until}）",
        weight_key="cert_expired", thr=thr,
    )


def fuse(evidences: list[Evidence], findings: list[Finding], thr: dict) -> Verdict:
    lv = thr.get("levels", {})
    cf = thr.get("confidence", {})

    down = sum(abs(e.weight) for e in evidences if e.polarity == Polarity.DOWN)
    up = sum(e.weight for e in evidences if e.polarity == Polarity.UP)
    risk = max(0.0, down - 0.5 * up)

    effective = [e for e in evidences if e.status in (
        EvidenceStatus.CONFIRMED, EvidenceStatus.CONTRADICTED, EvidenceStatus.NOT_FOUND)]
    unverifiable = [e for e in evidences if e.status == EvidenceStatus.UNVERIFIABLE]
    ratio = len(unverifiable) / max(1, len(evidences))

    fired: str | None = None
    for e in evidences:
        key = e.kind if e.kind in REDLINE_CN else None
        if key == "medical" and e.status == EvidenceStatus.CONFIRMED and thr.get("redlines", {}).get("medical_term_core"):
            fired = REDLINE_CN["medical"]
            break
        if key in ("cert", "filing", "institution", "expert") and e.status == EvidenceStatus.CONTRADICTED:
            if thr.get("redlines", {}).get(f"{key}_subject_mismatch") or thr.get("redlines", {}).get(f"{key}_contradicted"):
                fired = REDLINE_CN[key]
                break

    conf = float(cf.get("base", 0.4)) + float(cf.get("per_evidence", 0.08)) * len(effective) \
        - float(cf.get("unverifiable_penalty", 0.3)) * ratio
    conf = max(float(cf.get("min", 0.3)), min(float(cf.get("max", 0.95)), conf))

    if fired:
        level = VerdictLevel.HIGHLY_SUSPECTED
        conf = max(conf, float(cf.get("redline_floor", 0.9)))
        reason = f"命中红线：{fired}"
    elif len(effective) < int(lv.get("min_effective_evidence", 2)) or ratio > float(lv.get("max_unverifiable_ratio", 0.5)):
        level = VerdictLevel.INSUFFICIENT
        reason = f"有效证据 {len(effective)} 条，不可验占比 {ratio:.0%}，材料不足需补料"
    elif risk >= float(lv.get("high_risk_score", 8.0)):
        level = VerdictLevel.HIGHLY_SUSPECTED
        reason = f"风险分 {risk:.1f} ≥ {lv.get('high_risk_score')}"
    elif risk >= float(lv.get("doubtful_score", 4.0)):
        level = VerdictLevel.DOUBTFUL
        reason = f"风险分 {risk:.1f}，存在待核验冲突点"
    else:
        level = VerdictLevel.VERIFIABLE
        reason = f"风险分 {risk:.1f}，未发现实质冲突"

    high_findings = [f for f in findings if not f.ok and f.severity == "high"]
    if high_findings and level == VerdictLevel.VERIFIABLE:
        level = VerdictLevel.DOUBTFUL
        reason = f"{reason}；另有 {len(high_findings)} 项高危一致性/合规问题"

    return Verdict(level=level, level_cn=VERDICT_CN[level], risk_score=round(risk, 1),
                   confidence=round(conf, 2), fired_redline=fired, reason=reason)
