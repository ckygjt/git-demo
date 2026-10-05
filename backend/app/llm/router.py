"""多 Provider 路由：按 PROVIDER_ORDER 依次尝试 → 全部失败返回 None（调用方降级 Mock）。

- 只走 OpenAI 兼容协议，不绑定厂商
- 按 (tier, model, prompt, 图片哈希) 做磁盘缓存：重复演示零成本、结果稳定
- 返回 meta 用于成本统计
"""
import base64
import hashlib
import json
import logging
import re
from typing import Any

from ..config import CACHE, Provider, settings

log = logging.getLogger(__name__)
_clients: dict[str, Any] = {}


def _client(p: Provider):
    if p.name not in _clients:
        from openai import OpenAI

        kwargs = {"api_key": p.api_key, "timeout": settings().timeout}
        if p.base_url:
            kwargs["base_url"] = p.base_url
        _clients[p.name] = OpenAI(**kwargs)
    return _clients[p.name]


def _parse_json(text: str) -> dict | None:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _cache_path(key: str):
    d = CACHE / "llm"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{key}.json"


def chat_json(tier: str, system: str, user: str, images: list[bytes] | None = None) -> tuple[dict | None, dict]:
    """tier: 'vision' | 'text'。返回 (解析后的 JSON 或 None, meta)。"""
    s = settings()
    meta: dict[str, Any] = {"provider": None, "model": None, "cached": False, "tokens_in": 0, "tokens_out": 0, "errors": []}
    if s.mock:
        meta["provider"] = "mock"
        return None, meta

    img_hash = hashlib.sha256(b"".join(images or [])).hexdigest()
    for p in s.providers:
        model = p.vision_model if tier == "vision" else p.text_model
        if not model:
            continue
        key = hashlib.sha256(f"{tier}|{model}|{system}|{user}|{img_hash}".encode()).hexdigest()[:32]
        cp = _cache_path(key)
        if s.cache and cp.exists():
            meta.update(provider=p.name, model=model, cached=True)
            return json.loads(cp.read_text(encoding="utf-8")), meta

        content: list[dict] | str = user
        if images:
            content = [{"type": "text", "text": user}] + [
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(b).decode()}}
                for b in images
            ]
        try:
            resp = _client(p).chat.completions.create(
                model=model,
                temperature=0,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": content}],
            )
            data = _parse_json(resp.choices[0].message.content or "")
            if data is None:
                raise ValueError("non-JSON response")
            usage = getattr(resp, "usage", None)
            meta.update(
                provider=p.name, model=model,
                tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
                tokens_out=getattr(usage, "completion_tokens", 0) or 0,
            )
            if s.cache:
                cp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return data, meta
        except Exception as e:  # noqa: BLE001 —— 任何失败都切下一个 provider
            log.warning("provider %s failed: %s", p.name, e)
            meta["errors"].append(f"{p.name}: {type(e).__name__}")
    meta["provider"] = "mock"
    return None, meta
