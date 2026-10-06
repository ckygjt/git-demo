"""分级处置：结论 → 处置动作 → 补料清单 → 话术。"""

from __future__ import annotations

from ..schemas import Evidence, EvidenceStatus, VerdictLevel

ACTION_OF = {
    VerdictLevel.VERIFIABLE: "archive",
    VerdictLevel.DOUBTFUL: "human_review",
    VerdictLevel.HIGHLY_SUSPECTED: "takedown",
    VerdictLevel.INSUFFICIENT: "supplement",
}

ACTION_CN = {
    "archive": "归档留痕，可正常对外宣称",
    "human_review": "转人工复核",
    "takedown": "建议下架并整改对外宣称",
    "supplement": "补充材料后重跑核验",
}

MISSING_BY_KIND = {
    "cert": "证书原件高清扫描件（含印章与编号）",
    "filing": "国家药监局备案/注册信息截图",
    "institution": "发证机构资质证明（CMA/CNAS 证书）",
    "expert": "专家在职证明或公开任职信息链接",
    "reference": "被引文献/数据来源全文",
    "spread": "原发布链接与发布时间证明",
}


def supplement_requests(evidences: list[Evidence]) -> list[str]:
    asks: list[str] = []
    for e in evidences:
        if e.status == EvidenceStatus.UNVERIFIABLE:
            asks.append(f"[{e.tool_cn or e.tool}] 核验未完成（{e.summary or '工具不可用'}）：需人工补充 {MISSING_BY_KIND.get(e.kind, '相应证明材料')}")
        elif e.status == EvidenceStatus.NOT_FOUND:
            asks.append(f"[{e.tool_cn or e.tool}] 未检索到「{e.query}」：需提供 {MISSING_BY_KIND.get(e.kind, '相应证明材料')}")
    return list(dict.fromkeys(asks))


def script(action: str, asks: list[str], fired: str | None = None) -> str:
    if action == "takedown":
        head = f"核验证据显示存在伪造信源风险{'（' + fired + '）' if fired else ''}，建议立即下架相关素材并整改对外宣称，保留以下举证材料用于申诉或投诉。"
    elif action == "human_review":
        head = "核验存在待确认的冲突点，建议转人工复核后再对外发布，复核重点见补料清单。"
    elif action == "supplement":
        head = "现有材料不足以形成结论，请按补料清单补充后重跑核验。"
    else:
        head = "未发现实质冲突，建议归档留痕，并保留本次核验报告备查。"
    if asks:
        return head + "\n补料清单：\n" + "\n".join(f"- {a}" for a in asks)
    return head
