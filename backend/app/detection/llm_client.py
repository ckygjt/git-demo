"""大模型客户端：OpenAI 兼容协议，支持通义千问 / DeepSeek / OpenAI 自动切换。

设计要点：
- 未配置 Key 或调用失败时返回 None，由上层降级为纯本地取证，保证演示不断线。
"""
from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from .. import config

_client: OpenAI | None = None


def _build_client() -> OpenAI | None:
    if not config.API_KEY:
        return None
    return OpenAI(
        api_key=config.API_KEY,
        base_url=config.BASE_URL,
        timeout=config.LLM_TIMEOUT_SECONDS,
        max_retries=1,
    )


def get_client() -> OpenAI | None:
    global _client
    if _client is None:
        try:
            _client = _build_client()
        except Exception as exc:  # SDK/依赖异常也降级，绝不能拖垮接口
            print(f"[llm] 客户端构建失败，自动降级：{exc}")
            return None
    return _client


def available() -> bool:
    return config.ENABLE_LLM and get_client() is not None


def parse_json(raw: str | None) -> dict[str, Any] | None:
    """从 LLM 输出中稳健提取 JSON（容忍 ```json 代码块与前后废话）。"""
    if not raw:
        return None
    text = raw.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def chat(
    messages: list[dict[str, Any]],
    model: str | None = None,
    max_tokens: int = 700,
    temperature: float = 0.2,
) -> str | None:
    client = get_client()
    if client is None or not config.ENABLE_LLM:
        return None
    try:
        resp = client.chat.completions.create(
            model=model or config.TEXT_MODEL,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content
    except Exception as exc:  # 网络/额度/超时均降级
        print(f"[llm] 调用失败，自动降级：{exc}")
        return None


def chat_json(
    messages: list[dict[str, Any]],
    model: str | None = None,
    max_tokens: int = 700,
) -> dict[str, Any] | None:
    return parse_json(chat(messages, model=model, max_tokens=max_tokens))
