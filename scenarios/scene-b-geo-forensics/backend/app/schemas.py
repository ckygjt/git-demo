"""场景B 数据契约。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EvidenceStatus(str, Enum):
    """证据状态。关键设计：NOT_FOUND 不等于伪造。"""

    CONFIRMED = "confirmed"        # 信源存在且与声明一致
    CONTRADICTED = "contradicted"  # 信源存在但与声明冲突（强降信）
    NOT_FOUND = "not_found"        # 查无结果（不等于伪造）
    UNVERIFIABLE = "unverifiable"  # 工具失败/超时/无可用信源


class Polarity(str, Enum):
    UP = "up"
    DOWN = "down"
    NOTE = "note"


class VerdictLevel(str, Enum):
    VERIFIABLE = "verifiable"              # 可核验（低风险）
    DOUBTFUL = "doubtful"                  # 存疑
    HIGHLY_SUSPECTED = "highly_suspected"  # 高度疑似伪造
    INSUFFICIENT = "insufficient"          # 证据不足


VERDICT_CN = {
    VerdictLevel.VERIFIABLE: "可核验（低风险）",
    VerdictLevel.DOUBTFUL: "存疑",
    VerdictLevel.HIGHLY_SUSPECTED: "高度疑似伪造",
    VerdictLevel.INSUFFICIENT: "证据不足",
}

STATUS_CN = {
    EvidenceStatus.CONFIRMED: "证实",
    EvidenceStatus.CONTRADICTED: "冲突",
    EvidenceStatus.NOT_FOUND: "查无",
    EvidenceStatus.UNVERIFIABLE: "不可验",
}

POLARITY_CN = {Polarity.UP: "增信", Polarity.DOWN: "降信", Polarity.NOTE: "提示"}


class Artifact(BaseModel):
    name: str
    path: str
    sha256: str = ""
    width: int = 0
    height: int = 0
    mime: str = ""
    usable: bool = True
    note: str = ""


class Claim(BaseModel):
    type: str = Field(description="efficacy|data|endorsement|ranking|medical")
    type_cn: str = ""
    text: str
    entities: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    tool: str
    tool_cn: str = ""
    kind: str = ""
    query: str
    status: EvidenceStatus
    status_cn: str = ""
    polarity: Polarity = Polarity.NOTE
    polarity_cn: str = ""
    weight: float = 0.0
    summary: str = ""
    source_url: str | None = None
    captured_at: str = ""
    degraded: bool = False
    needs_human_review: bool = False
    elapsed_ms: int = 0


class Finding(BaseModel):
    dimension: str
    ok: bool
    detail: str
    severity: str = "medium"  # high | medium | low


class Verdict(BaseModel):
    level: VerdictLevel
    level_cn: str = ""
    risk_score: float = 0.0
    confidence: float = 0.0
    fired_redline: str | None = None
    reason: str = ""


class StepEvent(BaseModel):
    step: str
    title: str
    status: str = "done"  # running | done | error
    detail: str = ""
    elapsed_ms: int = 0
    data: dict[str, Any] | None = None


class CaseInput(BaseModel):
    text: str = ""
    source_url: str = ""
    brand: str = ""
    product: str = ""
    images: list[Artifact] = Field(default_factory=list)


class VerifyResult(BaseModel):
    case_id: str
    input: CaseInput
    mode: str = "mock"
    claims: list[Claim] = Field(default_factory=list)
    evidences: list[Evidence] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    verdict: Verdict | None = None
    missing_materials: list[str] = Field(default_factory=list)
    action: str = ""
    action_cn: str = ""
    script: str = ""
    plan: list[str] = Field(default_factory=list)
    cost: dict[str, Any] = Field(default_factory=dict)
    elapsed_ms: int = 0
    disclaimer: str = "本结论为信源伪造风险研判，不构成对任何主体的真伪定论、质量评价或法律意见，须经人工复核后使用。"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
