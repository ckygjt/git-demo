"""多模态 LLM：图像要素抽取（S1）与文本要素补充。

real：openai SDK 走 DashScope OpenAI 兼容端点，模型 qwen-vl-max-latest
mock：读取 config/mock_sources.yaml 的 vision_fixtures 回放
"""

from __future__ import annotations

import base64
import json
import logging

from ..config import mock_sources, settings

try:  # openai SDK 为可选依赖，缺失时自动降级为 mock
    from openai import OpenAI
except Exception:  # noqa: BLE001
    OpenAI = None  # type: ignore[assignment]

log = logging.getLogger(__name__)

VISION_PROMPT = (
    "你是证书与检测报告的要素抽取助手。请只依据图中可见内容抽取，无法确认的字段留空字符串。"
    '输出严格 JSON：{"doc_type":"certificate|report|expert_portrait|product|other","cert_no":"",'
    '"issuer":"","subject":"","valid_until":"YYYY-MM-DD","standard":"","scope":"","product":"",'
    '"brand":"","filing_no":"","person":"","org":"","title":""}'
)

TEXT_PROMPT = (
    "你是美妆合规要素抽取助手。从文本中抽取实体，输出严格 JSON："
    '{"orgs":[],"persons":[],"filing_no":[],"cert_no":[],"references":[]}。'
    "机构含协会/研究院/医院/检测/认证公司；人员含主任/医师/博士/研究员/教授；"
    "备案号形如 国妆网备字2025000001；证书号形如 CMA-2024-HZ-0451。"
)


def _match_fixture(filename: str) -> dict:
    fx = (mock_sources().get("vision_fixtures") or {})
    name = (filename or "").lower()
    for key in ("cert", "expert"):
        block = fx.get(key) or {}
        for kw in block.get("match", []):
            if str(kw).lower() in name:
                return {"doc_type": block.get("doc_type", key), **(block.get("fields") or {})}
    default = fx.get("default") or {}
    return {"doc_type": default.get("doc_type", "other"), **(default.get("fields") or {})}


def _data_uri(data: bytes, mime: str) -> str:
    return f"data:{mime or 'image/jpeg'};base64,{base64.b64encode(data).decode()}"


def vision_extract(image_bytes: bytes, filename: str, mime: str = "image/jpeg") -> dict:
    """抽取图片要素。失败一律降级，不抛异常。"""
    s = settings()
    if s.mock or OpenAI is None or not s.has_llm:
        return _match_fixture(filename)
    try:
        client = OpenAI(api_key=s.dashscope_api_key, base_url=s.dashscope_base_url)
        resp = client.chat.completions.create(
            model=s.vision_model,
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": _data_uri(image_bytes, mime)}},
                {"type": "text", "text": VISION_PROMPT},
            ]}],
            response_format={"type": "json_object"},
            timeout=s.timeout,
        )
        content = resp.choices[0].message.content or "{}"
        return json.loads(content)
    except Exception as e:  # noqa: BLE001
        log.warning("vision_extract 失败，降级为回放：%s", type(e).__name__)
        out = _match_fixture(filename)
        out["degraded"] = True
        return out


def text_extract(text: str) -> dict | None:
    """文本要素补充抽取。mock 模式返回 None（交给规则抽取）。"""
    s = settings()
    if s.mock or OpenAI is None or not s.has_llm or not text:
        return None
    try:
        client = OpenAI(api_key=s.dashscope_api_key, base_url=s.dashscope_base_url)
        resp = client.chat.completions.create(
            model=s.text_model,
            messages=[{"role": "user", "content": f"{TEXT_PROMPT}\n\n文本：{text[:2000]}"}],
            response_format={"type": "json_object"},
            timeout=s.timeout,
        )
        return json.loads(resp.choices[0].message.content or "{}")
    except Exception as e:  # noqa: BLE001
        log.warning("text_extract 失败，降级为规则抽取：%s", type(e).__name__)
        return None
