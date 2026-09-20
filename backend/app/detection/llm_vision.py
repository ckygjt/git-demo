"""多模态视觉分析（软证据）：判断图像是否存在 AI 生成、拼接、过度修饰痕迹。"""
from __future__ import annotations

import base64

from .. import config
from ..schemas import Evidence
from . import llm_client

SYSTEM_PROMPT = (
    "你是美妆电商内容风控专家，擅长图像取证。请判断图片是否为真实拍摄的化妆品/美妆内容图，"
    "重点关注：AI 生成痕迹、拼接合成、局部磨皮换肤、盗用官方图、伪造检测报告或资质证书。"
    "只输出 JSON，字段为：ai_generated(0~1)、splicing(0~1)、over_retouch(0~1)、"
    "suspicious(bool)、findings(字符串数组，每条不超过 30 字)、reason(一句话结论)。"
)


def _to_data_url(data: bytes, mime: str = "image/jpeg") -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def analyze(image_bytes: bytes, mime: str = "image/jpeg") -> Evidence | None:
    """返回一条语义级证据；LLM 不可用时返回 None（由上层降级）。"""
    if not config.VISION_ENABLED:
        return None

    payload = llm_client.chat_json(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": _to_data_url(image_bytes, mime)}},
                    {"type": "text", "text": "请对这张美妆内容图做真伪分析，输出 JSON。"},
                ],
            },
        ],
        model=config.VISION_MODEL,
        max_tokens=500,
    )
    if not payload:
        return None

    def _f(key: str) -> float:
        try:
            return max(0.0, min(1.0, float(payload.get(key, 0.0))))
        except (TypeError, ValueError):
            return 0.0

    ai, splice, retouch = _f("ai_generated"), _f("splicing"), _f("over_retouch")
    score = max(ai, splice, retouch * 0.7)
    findings = payload.get("findings") or []
    reason = str(payload.get("reason", "")).strip()

    desc = reason or "；".join(str(x) for x in findings[:3]) or "视觉模型未发现明显异常"
    if ai >= 0.5:
        name = "视觉模型判定疑似 AI 生成"
    elif splice >= 0.5:
        name = "视觉模型判定疑似拼接合成"
    elif retouch >= 0.5:
        name = "视觉模型判定疑似过度修饰"
    else:
        name = "视觉语义分析"

    return Evidence(
        source="vision_llm",
        name=name,
        score=round(score, 3),
        weight=config.EVIDENCE_WEIGHT["vision_llm"],
        description=f"{desc}（AI生成{ai:.2f} / 拼接{splice:.2f} / 修饰{retouch:.2f}）",
        severity="high" if score >= 0.6 else "medium" if score >= 0.35 else "low",
    )
