"""S4 诉求理解 + S5 聊天首次原因。规则快路径，LLM 兜底（真实模式）。"""
import re

from ..llm.router import chat_json
from ..schemas import ClaimInfo, IssueType

HEALTH = re.compile(r"过敏|红疹|刺痛|不适|烂脸|红肿|发痒|很痒|起痘|灼")
ISSUE_PATTERNS: list[tuple[IssueType, re.Pattern]] = [
    (IssueType.wrong_item, re.compile(r"错发|发错|不是我买的|货不对")),
    (IssueType.missing_item, re.compile(r"少件|漏发|少了|缺了|没收到赠品")),
    (IssueType.leak, re.compile(r"漏液|漏了|渗|漏出|溢出")),
    (IssueType.pump_broken, re.compile(r"泵头.*(断|坏|按不出|歪)|按不出")),
    (IssueType.container_crack, re.compile(r"碎|裂")),
    (IssueType.outer_box_damage, re.compile(r"盒子|外包装|外盒|压扁|压坏|包装破损")),
]
PART_PATTERNS = [
    ("pump_head", re.compile(r"泵头")),
    ("bottle_neck", re.compile(r"瓶口|滴管")),
    ("jar_body", re.compile(r"罐")),
    ("outer_box", re.compile(r"盒|外包装")),
    ("bottle_body", re.compile(r"瓶身|瓶子")),
    ("tube_crimp", re.compile(r"封口|尾部")),
]
NON_QUALITY = re.compile(r"不喜欢|味道|不想要|买错|不合适|用不完|太贵")
ON_ARRIVAL = re.compile(r"刚收到|收到就|到货|一拿到|拆开就")
AFTER_USE = re.compile(r"用了|使用后")

LLM_SYSTEM = """从售后申请中抽取结构化诉求，严格输出 JSON：
{"issue_type": "outer_box_damage|container_crack|pump_broken|leak|missing_item|wrong_item|quality|allergy|other",
 "part": 部位英文或null, "time_hint": "on_arrival|after_use"或null, "claimed_qty": 整数}"""


def _match_issue(text: str) -> IssueType | None:
    for issue, pat in ISSUE_PATTERNS:
        if pat.search(text):
            return issue
    return None


def classify_reason(text: str) -> str | None:
    """聊天单句归类：health / 具体问题类型 / non_quality / None。"""
    if HEALTH.search(text):
        return "allergy"
    issue = _match_issue(text)
    if issue:
        return issue.value
    if NON_QUALITY.search(text):
        return "non_quality"
    return None


def parse(ticket: dict, chat: dict | None) -> ClaimInfo:
    text = f"{ticket.get('reason', '')} {ticket.get('description', '')}"
    first_buyer = next((m["text"] for m in (chat or {}).get("messages", []) if m["role"] == "buyer"), None)
    info = ClaimInfo(chat_first_reason=classify_reason(first_buyer) if first_buyer else None)

    if HEALTH.search(text):
        info.issue_type, info.is_health_claim = IssueType.allergy, True
        return info

    issue = _match_issue(ticket.get("description", "")) or _match_issue(ticket.get("reason", ""))
    if issue is None:
        data, _ = chat_json("text", LLM_SYSTEM, text)
        if data and data.get("issue_type") in IssueType._value2member_map_:
            info.issue_type = IssueType(data["issue_type"])
            info.part = data.get("part")
            info.time_hint = data.get("time_hint")
            info.parsed_by = "llm"
            info.is_health_claim = info.issue_type == IssueType.allergy
            return info
    else:
        info.issue_type = issue

    if info.issue_type == IssueType.outer_box_damage:
        info.part = "outer_box"
    else:
        info.part = next((p for p, pat in PART_PATTERNS if p != "outer_box" and pat.search(text)), None)
    info.time_hint = "on_arrival" if ON_ARRIVAL.search(text) else ("after_use" if AFTER_USE.search(text) else None)
    return info
