"""Step6 处置映射、补拍要求、话术（含禁用词护栏）。结论→处置走查表，不经 LLM。"""
from ..schemas import Action, Evidence, Verdict

ACTION_OF = {
    Verdict.credible: Action.direct_process,
    Verdict.doubtful_insufficient: Action.request_more_evidence,
    Verdict.doubtful_suspicious: Action.switch_to_return,
    Verdict.high_risk: Action.return_inspect_review,
    Verdict.health_referral: Action.refer_specialist,
}

FORBIDDEN = ["怀疑", "造假", "伪造", "风险", "P图", "骗", "作假", "虚假", "可疑", "欺诈", "恶意"]

SCRIPTS = {
    Action.direct_process: "亲，非常抱歉给您带来不便～这边已为您登记处理，款项会尽快原路退回，请您留意到账哦。",
    Action.request_more_evidence: "亲，为了帮您更快处理，麻烦您{ask}，我们收到后会马上为您跟进～",
    Action.switch_to_return: "亲，非常抱歉让您遇到这个问题～为了尽快帮您处理，这边为您安排上门取件，运费由我们承担，商品寄回后马上为您办理退款哦。",
    Action.return_inspect_review: "亲，非常抱歉让您遇到这个问题～这边为您安排上门取件，运费由我们承担，商品寄回后会第一时间为您办理退款，请您放心。",
    Action.refer_specialist: "亲，听到您用后不适我们非常担心，请您先停止使用。我们的专属顾问会尽快联系您，了解情况并协助处理，也建议您必要时及时就医。",
}

ACTION_CN = {
    Action.direct_process: "按诉求直接处理",
    Action.request_more_evidence: "定向补充凭证",
    Action.switch_to_return: "改为退货退款（商家承担运费 / 上门取件）",
    Action.return_inspect_review: "退货退款 + 仓库重点验收 + 二线复核",
    Action.refer_specialist: "转专人跟进（消费者关怀）",
}
VERDICT_CN = {
    Verdict.credible: "可信", Verdict.doubtful_insufficient: "存疑 · 信息不足", Verdict.doubtful_suspicious: "存疑 · 有疑点",
    Verdict.high_risk: "高风险", Verdict.health_referral: "健康类 · 转专人",
}


def supplement_requests(ev: list[Evidence], limit: int = 2) -> list[str]:
    out: list[str] = []
    for e in ev:
        ask = e.detail.get("supplement")
        if ask and e.polarity == "down" and ask not in out:
            out.append(ask)
    return out[:limit]


def safe(text: str, fallback: str) -> str:
    return fallback if any(w in text for w in FORBIDDEN) else text


def script(action: Action, asks: list[str]) -> str:
    tpl = SCRIPTS[action]
    if action == Action.request_more_evidence:
        ask = "，并".join(a.removeprefix("请") for a in asks) if asks else "再补拍一张清晰的破损位置照片"
        tpl = tpl.format(ask=ask)
    return safe(tpl, SCRIPTS[Action.switch_to_return])
