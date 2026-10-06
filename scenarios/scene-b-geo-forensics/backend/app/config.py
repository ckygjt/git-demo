"""场景B 配置：路径、运行模式、阈值。

运行模式：
- mock：未配置任何 Key，或 AGENT_MODE=mock —— 全部走本地信源库回放
- real：AGENT_MODE=real 且至少配置一个 Key
- auto（默认）：有 Key 走真实调用，单工具失败自动降级，主流程不中断
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

# scenarios/scene-b-geo-forensics/backend/app/config.py
ROOT = Path(__file__).resolve().parents[2]  # scene-b-geo-forensics
BACKEND = ROOT / "backend"
CONFIG = BACKEND / "config"
DATA = ROOT / "data"
UPLOADS = DATA / "uploads"
CASES = DATA / "cases"
WEB = ROOT / "web"

REPO_ROOT = Path(__file__).resolve().parents[4]
for env_path in (REPO_ROOT / ".env", ROOT / ".env"):
    if env_path.exists():
        load_dotenv(env_path, override=False)


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


@dataclass
class Settings:
    mode: str  # mock | real | auto
    dashscope_api_key: str
    dashscope_base_url: str
    vision_model: str
    text_model: str
    tavily_api_key: str
    nmpa_base_url: str
    timeout: float
    cache: bool

    @property
    def has_llm(self) -> bool:
        return bool(self.dashscope_api_key)

    @property
    def has_search(self) -> bool:
        return bool(self.tavily_api_key)

    @property
    def mock(self) -> bool:
        """是否走本地回放。real 模式下强制不回放。"""
        if self.mode == "mock":
            return True
        if self.mode == "real":
            return False
        return not (self.has_llm or self.has_search)

    @property
    def effective(self) -> str:
        return "mock" if self.mock else "real"


@lru_cache
def settings() -> Settings:
    return Settings(
        mode=(_env("AGENT_MODE", "auto") or "auto").lower(),
        dashscope_api_key=_env("DASHSCOPE_API_KEY"),
        dashscope_base_url=_env("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        vision_model=_env("DASHSCOPE_VISION_MODEL", "qwen-vl-max-latest"),
        text_model=_env("DASHSCOPE_TEXT_MODEL", "qwen-plus"),
        tavily_api_key=_env("TAVILY_API_KEY"),
        nmpa_base_url=_env("NMPA_SEARCH_URL", "https://hzpba.nifdc.org.cn/pc/home/search"),
        timeout=float(_env("TOOL_TIMEOUT_SECONDS", "15")),
        cache=_env("TOOL_CACHE", "true").lower() == "true",
    )


@lru_cache
def thresholds() -> dict:
    with open(CONFIG / "thresholds.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache
def mock_sources() -> dict:
    """本地虚构信源库（演示用，全部虚构，不指向任何真实主体）。"""
    with open(CONFIG / "mock_sources.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def ensure_dirs() -> None:
    for p in (UPLOADS, CASES):
        p.mkdir(parents=True, exist_ok=True)
