"""工具适配层统一契约。

所有核验工具（备案库、证书库、机构、专家、检索、传播）都返回同一个 CheckOutcome，
从而让 mock / real 两种实现可以互换，且失败语义统一。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..schemas import EvidenceStatus


@dataclass
class CheckRequest:
    kind: str            # filing | cert | institution | expert | reference | spread
    value: str
    brand: str = ""
    org: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class CheckOutcome:
    status: EvidenceStatus
    summary: str
    source_url: str | None = None
    confidence: float = 0.6
    degraded: bool = False      # 真实调用失败后降级
    needs_human_review: bool = False
    data: dict = field(default_factory=dict)


def unverifiable(reason: str) -> CheckOutcome:
    return CheckOutcome(
        status=EvidenceStatus.UNVERIFIABLE,
        summary=reason,
        confidence=0.0,
        degraded=True,
        needs_human_review=True,
    )
