"""数据契约：前后端唯一事实来源。"""
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class IssueType(str, Enum):
    outer_box_damage = "outer_box_damage"
    container_crack = "container_crack"
    pump_broken = "pump_broken"
    leak = "leak"
    missing_item = "missing_item"
    wrong_item = "wrong_item"
    quality = "quality"
    allergy = "allergy"
    other = "other"


class Source(str, Enum):
    S1 = "S1"  # 像素取证
    S2 = "S2"  # 视觉内容
    S3 = "S3"  # 元数据
    S4 = "S4"  # 诉求
    S5 = "S5"  # 聊天
    S6 = "S6"  # 订单
    S7 = "S7"  # 物流
    S8 = "S8"  # 账号
    S9 = "S9"  # 跨工单
    S10 = "S10"  # 产品知识
    S11 = "S11"  # 批次群体
    S12 = "S12"  # 流程新证据
    S0 = "S0"  # 预处理（图像质量）


SOURCE_LABEL = {
    "S0": "图像质量", "S1": "像素取证", "S2": "图像内容", "S3": "图片元数据", "S4": "诉求文本",
    "S5": "聊天记录", "S6": "订单", "S7": "物流", "S8": "账号历史", "S9": "跨工单",
    "S10": "产品知识库", "S11": "批次投诉", "S12": "补充证据",
}


class Polarity(str, Enum):
    up = "up"      # 增信
    down = "down"  # 降信
    note = "note"  # 仅备注（如与诉求无关的编辑）


class Strength(str, Enum):
    strong = "strong"
    medium = "medium"
    weak = "weak"


class Verdict(str, Enum):
    credible = "credible"
    doubtful_insufficient = "doubtful_insufficient"
    doubtful_suspicious = "doubtful_suspicious"
    high_risk = "high_risk"
    health_referral = "health_referral"


class Action(str, Enum):
    direct_process = "direct_process"
    request_more_evidence = "request_more_evidence"
    switch_to_return = "switch_to_return"
    return_inspect_review = "return_inspect_review"
    refer_specialist = "refer_specialist"


class Evidence(BaseModel):
    id: str = ""
    source: Source
    rule: str                       # 触发规则编号，如 X2_spec_mismatch
    polarity: Polarity
    strength: Strength
    claim_relevant: bool = True
    resolvable: bool = False        # 补拍即可澄清的疑点
    confidence: float = 0.8
    summary: str
    locator: dict[str, Any] | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class ClaimInfo(BaseModel):
    issue_type: IssueType = IssueType.other
    part: str | None = None
    time_hint: str | None = None      # on_arrival / after_use / None
    claimed_qty: int = 1
    is_health_claim: bool = False
    chat_first_reason: str | None = None
    parsed_by: str = "rule"


class ToolOutput(BaseModel):
    tool: str
    source: Source
    ok: bool = True
    mode: str = "local"               # local / llm / mock
    evidence: list[Evidence] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    elapsed_ms: int = 0


class StepEvent(BaseModel):
    step: str
    title: str
    status: str                       # running / done / error / skipped
    detail: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    elapsed_ms: int = 0


class VerifyResult(BaseModel):
    ticket_id: str
    verdict: Verdict
    action: Action
    fired_rule: str
    reason: str
    confidence: float
    claim: ClaimInfo
    plan: list[str]
    evidence: list[Evidence]
    flags: list[Evidence]
    supplement_requests: list[str]
    script: str
    tools: list[ToolOutput]
    mode: str
    cost: dict[str, Any] = Field(default_factory=dict)
    elapsed_ms: int = 0
