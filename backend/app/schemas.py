"""前后端共用的数据契约（唯一真相源）。改动前请在群里同步。"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

EvidenceSource = Literal["forensics", "vision_llm", "text_rule", "text_llm"]
RiskLevel = Literal["low", "medium", "high"]
ActionType = Literal["pass", "review", "flag", "takedown"]


class Evidence(BaseModel):
    """单条证据：既能参与打分，也能在前端解释与定位。"""

    source: EvidenceSource
    name: str
    score: float = Field(ge=0.0, le=1.0, description="0~1，越高越可疑")
    weight: float = Field(default=0.1, description="Agent 聚合权重")
    description: str
    region: Optional[list[float]] = Field(
        default=None, description="可疑区域归一化坐标 [x, y, w, h]"
    )
    severity: str = Field(default="medium", description="low/medium/high")


class ImageAnalysis(BaseModel):
    width: int = 0
    height: int = 0
    format: str = ""
    heatmap: Optional[str] = Field(default=None, description="base64 PNG 热力图")
    evidence: list[Evidence] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    image_score: float = Field(default=0.0, description="0~100 图像侧综合可疑度")


class TextAnalysis(BaseModel):
    evidence: list[Evidence] = Field(default_factory=list)
    hits: list[str] = Field(default_factory=list)
    text_score: float = Field(default=0.0, description="0~100 文案侧综合可疑度")
    redline: bool = Field(default=False, description="是否命中合规红线")
    advice: list[str] = Field(default_factory=list)


class RiskReport(BaseModel):
    risk_level: RiskLevel
    risk_score: float = Field(description="0~100")
    action: ActionType
    reasoning: str
    suggestions: list[str] = Field(default_factory=list)
    image: Optional[ImageAnalysis] = None
    text: Optional[TextAnalysis] = None
    degraded: bool = Field(default=False, description="LLM 不可用时降级为本地取证")
    elapsed_ms: int = 0


class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class HealthResponse(BaseModel):
    status: str
    llm_provider: str
    llm_enabled: bool
    vision_enabled: bool
