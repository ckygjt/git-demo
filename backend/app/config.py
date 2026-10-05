import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
DATA = ROOT / "data"
SEED = DATA / "seed"
FIXTURES = SEED / "fixtures"
IMAGES = DATA / "images"
CACHE = DATA / "cache"

load_dotenv(ROOT / ".env")


@dataclass
class Provider:
    name: str
    api_key: str
    base_url: str
    vision_model: str | None
    text_model: str | None


@dataclass
class Settings:
    providers: list[Provider] = field(default_factory=list)
    timeout: float = 40.0
    cache: bool = True

    @property
    def mock(self) -> bool:
        return not self.providers


def _provider(name: str) -> Provider | None:
    p = name.upper()
    key = os.getenv(f"{p}_API_KEY", "").strip()
    if not key:
        return None
    return Provider(
        name=name,
        api_key=key,
        base_url=os.getenv(f"{p}_BASE_URL", "").strip(),
        vision_model=os.getenv(f"{p}_VISION_MODEL") or None,
        text_model=os.getenv(f"{p}_TEXT_MODEL") or None,
    )


@lru_cache
def settings() -> Settings:
    order = [x.strip() for x in os.getenv("PROVIDER_ORDER", "dashscope,openai,deepseek").split(",") if x.strip()]
    providers = [p for p in (_provider(n) for n in order) if p]
    return Settings(
        providers=providers,
        timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "40")),
        cache=os.getenv("LLM_CACHE", "true").lower() == "true",
    )


@lru_cache
def thresholds() -> dict:
    with open(BACKEND / "config" / "thresholds.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)
