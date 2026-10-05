"""RiskAgent 决策层：证据聚合 → 风险分级 → 处置动作 → 理由与建议。

设计原则：
1. 业务红线优先于统计分数（命中医疗功效/伪造资质直接建议下架）
2. LLM 用于生成人类可读的推理；不可用时退化为模板，保证闭环完整
"""
from __future__ import annotations

import time

from .. import config
from ..detection import llm_client
from ..schemas import Evidence, ImageAnalysis, RiskReport, TextAnalysis, ActionType

ACTION_LABEL = {
    "pass": "通过上架",
    "review": "转人工复核",
    "flag": "警示标记并限流",
    "takedown": "建议下架并触发合规工单",
}


def _aggregate(evidence: list[Evidence]) -> float:
    """加权平均得到 0~100 的风险总分。"""
    if not evidence:
        return 0.0
    total_w = sum(e.weight for e in evidence) or 1.0
    weighted = sum(e.score * e.weight for e in evidence)
    return round(100.0 * weighted / total_w, 2)


def _grade(score: float, redline: bool) -> tuple[str, ActionType]:
    if redline or score >= config.THRESHOLD_TAKEDOWN:
        return "high", "takedown"
    if score >= config.THRESHOLD_HIGH:
        return "high", "flag"
    if score >= config.THRESHOLD_MEDIUM:
        return "medium", "review"
    return "low", "pass"


def _suggestions(action: ActionType, redline: bool, advice: list[str]) -> list[str]:
    base = {
        "takedown": [
            "立即下架该内容并留存取证快照，作为后续申诉依据",
            "向创作者推送合规整改通知，说明具体违规条款",
            "将同账号历史内容纳入批量复检队列",
        ],
        "flag": [
            "对该内容添加'未经证实功效'警示标签并降低推荐权重",
            "要求创作者补充资质证明或功效评价报告",
            "48 小时内未整改则自动转为下架",
        ],
        "review": [
            "转入人工复核队列，优先查看取证热力图标记区域",
            "提示审核员重点核对功效表述与成分表一致性",
            "复核通过后可正常展示并保留检测记录",
        ],
        "pass": [
            "正常上架展示，检测报告归档留存",
            "纳入例行抽检池，按周复检",
        ],
    }[action]
    if redline and action != "takedown":
        base.insert(0, "命中宣称合规红线，建议升级为下架处理")
    return base + advice[:2]


def _template_reason(score: float, level: str, action: ActionType,
                     evidence: list[Evidence], redline: bool) -> str:
    top = sorted(evidence, key=lambda e: e.score * e.weight, reverse=True)[:3]
    detail = "；".join(f"{e.name}（置信度 {e.score:.2f}）" for e in top)
    head = "命中宣称合规红线，" if redline else ""
    return (
        f"{head}综合 {len(evidence)} 条证据加权聚合得风险分 {score:.1f}，"
        f"主要依据：{detail}。判定为{ {'low': '低', 'medium': '中', 'high': '高'}[level] }风险，"
        f"处置动作：{ACTION_LABEL[action]}。"
    )


def _llm_reason(score: float, action: ActionType, evidence: list[Evidence],
                redline: bool) -> str | None:
    if not config.ENABLE_LLM:
        return None
    lines = "\n".join(
        f"- [{e.source}] {e.name}：score={e.score:.2f}，weight={e.weight}，{e.description}"
        for e in evidence
    )
    payload = llm_client.chat_json(
        [
            {
                "role": "system",
                "content": (
                    "你是美妆内容风控决策 Agent。基于证据列表给出决策理由，"
                    "只输出 JSON：reasoning(80字内的中文推理)、confidence(0~1)。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"风险总分：{score}\n红线命中：{redline}\n"
                    f"建议动作：{ACTION_LABEL[action]}\n证据列表：\n{lines}"
                ),
            },
        ],
        model=config.TEXT_MODEL,
        max_tokens=300,
    )
    if not payload:
        return None
    reason = str(payload.get("reasoning", "")).strip()
    return reason or None


def decide(image: ImageAnalysis | None = None,
           text: TextAnalysis | None = None) -> RiskReport:
    started = time.perf_counter()

    evidence: list[Evidence] = []
    if image:
        evidence.extend(image.evidence)
    if text:
        evidence.extend(text.evidence)

    score = _aggregate(evidence)
    redline = bool(text and text.redline)
    level, action = _grade(score, redline)

    advice = list(text.advice) if text else []
    reasoning = _llm_reason(score, action, evidence, redline) or _template_reason(
        score, level, action, evidence, redline
    )
    degraded = not config.ENABLE_LLM

    return RiskReport(
        risk_level=level,
        risk_score=score,
        action=action,
        reasoning=reasoning,
        suggestions=_suggestions(action, redline, advice),
        image=image,
        text=text,
        degraded=degraded,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )
