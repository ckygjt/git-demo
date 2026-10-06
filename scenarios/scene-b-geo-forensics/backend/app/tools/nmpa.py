"""国家药监局化妆品备案/注册核验适配器。

real：先尝试抓取公开查询页（NMPA_SEARCH_URL 可配置），失败则退化为限定站点检索；
      仍失败 → UNVERIFIABLE（绝不把抓取失败当成伪造）
mock：读取 config/mock_sources.yaml 的 filings
"""

from __future__ import annotations

import logging

from ..config import mock_sources, settings
from ..schemas import EvidenceStatus
from .base import CheckOutcome, CheckRequest, unverifiable
from .search import tavily

try:
    import httpx
except Exception:  # noqa: BLE001
    httpx = None  # type: ignore[assignment]

log = logging.getLogger(__name__)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) geo-forensics-agent/0.1"}


def _scrape(no: str) -> tuple[bool, str | None]:
    """抓取公开查询页。返回 (是否命中, 来源 URL)。"""
    s = settings()
    if httpx is None:
        return False, None
    try:
        r = httpx.get(s.nmpa_base_url, params={"keyword": no}, headers=UA,
                      timeout=s.timeout, follow_redirects=True)
        if r.status_code != 200:
            return False, None
        return (no in r.text), str(r.url)
    except Exception as e:  # noqa: BLE001
        log.warning("药监局查询页抓取失败：%s", type(e).__name__)
        return False, None


def check_filing(req: CheckRequest) -> CheckOutcome:
    no = (req.value or "").strip()
    if not no:
        return unverifiable("未提供备案号")

    if settings().mock:
        src = (mock_sources().get("filings") or {}).get(no)
        if not src:
            return CheckOutcome(EvidenceStatus.NOT_FOUND, f"本地备案库未收录备案号 {no}",
                                confidence=0.5, needs_human_review=True)
        brand = (req.brand or "").strip()
        if brand and src.get("brand") and src["brand"] != brand:
            return CheckOutcome(
                EvidenceStatus.CONTRADICTED,
                f"备案号 {no} 对应品牌为「{src['brand']}」，与宣称品牌「{brand}」不一致",
                confidence=0.8, needs_human_review=True, data=src)
        return CheckOutcome(
            EvidenceStatus.CONFIRMED,
            f"备案号 {no} 已收录：{src.get('product', '')}（{src.get('category', '')}，核定范围 {'、'.join(src.get('scope') or [])}）",
            confidence=0.8, data=src)

    hit, url = _scrape(no)
    if hit:
        return CheckOutcome(EvidenceStatus.CONFIRMED, f"药监局查询页命中备案号 {no}",
                            source_url=url, confidence=0.6, needs_human_review=True)

    results = tavily(f"{no} site:nmpa.gov.cn")
    if results is None:
        return unverifiable("药监局查询页不可用，且检索工具未配置")
    if results:
        return CheckOutcome(EvidenceStatus.CONFIRMED, f"官方站点检索命中 {len(results)} 条",
                            source_url=results[0].get("url"), confidence=0.5,
                            needs_human_review=True, data={"count": len(results)})
    return CheckOutcome(EvidenceStatus.NOT_FOUND, f"药监局未检索到备案号 {no}",
                        confidence=0.5, needs_human_review=True)
