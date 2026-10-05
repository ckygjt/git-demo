"""Step5 证据融合与裁决：确定性规则，按顺序短路（需求 7.2）。

- 弱信号（strength=weak）与 note 只展示，不参与计数
- "可补拍澄清"(resolvable) 的内容冲突只能导向"存疑-信息不足"，不能单独推高到高风险
- 高风险 = 不可由补拍澄清的强降信（取证/同图多单）+ 另有印证；精确同图多单可单独成立
- 强增信可将"存疑"下调为"可信"；高风险不被抵消
"""
from ..config import thresholds
from ..schemas import Evidence, Polarity, Strength, Verdict


def _downs(ev: list[Evidence]) -> list[Evidence]:
    return [e for e in ev if e.polarity == Polarity.down and e.claim_relevant and e.strength != Strength.weak]


def confidence(ev: list[Evidence], tool_errors: int = 0) -> float:
    used = [e.confidence for e in ev if e.strength != Strength.weak and e.polarity != Polarity.note]
    base = sum(used) / len(used) if used else 0.8
    return round(max(0.0, base - thresholds()["fusion"]["tool_error_penalty"] * tool_errors), 2)


def decide(ev: list[Evidence], is_health: bool = False, tool_errors: int = 0) -> tuple[Verdict, str, str, float]:
    """返回 (结论, 触发规则, 一句话理由, 置信度)。"""
    conf = confidence(ev, tool_errors)
    if is_health:
        return Verdict.health_referral, "R0", "健康安全类诉求，转专人跟进，不走防骗逻辑", conf

    quality = [e for e in ev if e.rule == "Q_quality"]
    if quality:
        return Verdict.doubtful_insufficient, "R1", quality[0].summary + "，需补充清晰凭证", conf

    downs = _downs(ev)
    strong = [e for e in downs if e.strength == Strength.strong]
    hard = [e for e in strong if not e.resolvable]
    strong_up = [e for e in ev if e.polarity == Polarity.up and e.strength == Strength.strong]

    exact = next((e for e in strong if e.rule == "S9_exact_dup"), None)
    if exact:
        return Verdict.high_risk, "R2a", exact.summary, conf
    if hard and len(downs) >= 2:
        others = [e for e in downs if e is not hard[0]]
        return Verdict.high_risk, "R2", f"{hard[0].summary}；另有印证：{others[0].summary}", conf

    flagged = bool(strong) or len(downs) >= 2
    if flagged:
        if strong_up:
            return Verdict.credible, "R5-offset", f"存在疑点但{strong_up[0].summary}，予以增信", conf
        if all(e.resolvable for e in downs):
            return Verdict.doubtful_insufficient, "R3a", downs[0].summary + "，建议补充凭证澄清", conf
        return Verdict.doubtful_suspicious, "R3" if strong else "R4", downs[0].summary, conf

    if conf < thresholds()["fusion"]["min_confidence"]:
        return Verdict.doubtful_insufficient, "R1b", "证据置信度不足，建议补充凭证", conf
    note = next((e for e in ev if e.polarity == Polarity.note), None)
    return Verdict.credible, "R5", "未发现与诉求相关的疑点" + (f"；备注：{note.summary}" if note else ""), conf
