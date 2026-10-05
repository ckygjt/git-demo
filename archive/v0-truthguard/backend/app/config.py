"""全局配置：从 .env 读取，未提供 Key 时自动降级为纯本地取证模式。"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _flag(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


# ---------- 服务 ----------
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
MAX_EDGE = int(os.getenv("MAX_EDGE", "1024"))  # 图像分析前缩放到最长边

# ---------- LLM 供应商（按优先级自动选择） ----------
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "").strip()
DASHSCOPE_BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
).strip()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()

LLM_PROVIDER = ""
TEXT_MODEL = ""
VISION_MODEL = ""
API_KEY = ""
BASE_URL = ""

if DASHSCOPE_API_KEY:
    LLM_PROVIDER = "dashscope"
    API_KEY = DASHSCOPE_API_KEY
    BASE_URL = DASHSCOPE_BASE_URL
    TEXT_MODEL = os.getenv("TEXT_MODEL", "qwen-plus")
    VISION_MODEL = os.getenv("VISION_MODEL", "qwen-vl-max-latest")
elif DEEPSEEK_API_KEY:
    LLM_PROVIDER = "deepseek"
    API_KEY = DEEPSEEK_API_KEY
    BASE_URL = DEEPSEEK_BASE_URL
    TEXT_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    VISION_MODEL = ""  # DeepSeek 无视觉能力，视觉通道自动关闭
elif OPENAI_API_KEY:
    LLM_PROVIDER = "openai"
    API_KEY = OPENAI_API_KEY
    BASE_URL = OPENAI_BASE_URL
    TEXT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    VISION_MODEL = os.getenv("VISION_MODEL", "gpt-4o-mini")

ENABLE_LLM = _flag("ENABLE_LLM") and bool(LLM_PROVIDER)
VISION_ENABLED = ENABLE_LLM and bool(VISION_MODEL)
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

# ---------- 检测权重（与 docs/02-技术架构.md 保持一致） ----------
IMAGE_BLEND = {"ela": 0.45, "noise": 0.30, "metadata": 0.25}

EVIDENCE_WEIGHT = {
    "ela": 0.25,
    "noise": 0.15,
    "metadata": 0.10,
    "vision_llm": 0.20,
    "text_rule": 0.15,
    "text_llm": 0.15,
}

# ---------- 风险分级阈值 ----------
THRESHOLD_MEDIUM = 30.0  # >= 30 中风险
THRESHOLD_HIGH = 60.0  # >= 60 高风险
THRESHOLD_TAKEDOWN = 80.0  # >= 80 建议下架
