"""Step4 交叉验证：把各工具的原始观察转成带方向/强度/相关性的证据（需求 5、7 章）。

纯函数，不调用模型，便于单测。
"""
from dataclasses import dataclass, field
from typing import Any

from ..config import thresholds
from ..repo import parse_time
from ..schemas import ClaimInfo, Evidence, IssueType, Polarity as P, Source as S, Strength as St

DAMAGE_ISSUES = {IssueType.leak, IssueType.container_crack, IssueType.pump_broken, IssueType.outer_box_damage}
ISSUE_CN = {"leak": "漏液", "container_crack": "容器破裂", "pump_broken": "泵头损坏", "outer_box_damage": "外盒破损",
            "missing_item": "少件", "wrong_item": "错发", "other": "其他"}
CONTAINER_CN = {"glass_bottle": "玻璃瓶", "plastic_bottle": "塑料瓶", "plastic_tube": "软管", "glass_jar": "玻璃罐", "aluminum_tube": "铝管"}


@dataclass
class Observations:
    ticket: dict
    claim: ClaimInfo
    order: dict | None = None
    product: dict | None = None
    quality: dict[str, dict] = field(default_factory=dict)
    vision: dict[str, dict] = field(default_factory=dict)
    pixel: dict[str, dict] = field(default_factory=dict)
    exif: dict[str, dict] = field(default_factory=dict)
    logistics: dict[str, Any] = field(default_factory=dict)
    account: dict[str, Any] = field(default_factory=dict)
    dup: dict[str, Any] = field(default_factory=dict)
    batch: dict[str, Any] = field(default_factory=dict)


def _overlap(a: list | None, b: list | None) -> float:
    """交集 / 较小框面积。"""
    if not a or not b:
        return 0.0
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return inter / small if small > 0 else 0.0


def _same_color(a: str, b: str) -> bool:
    norm = lambda s: s.replace("色", "").replace("淡", "").replace("浅", "")  # noqa: E731
    a, b = norm(a), norm(b)
    return a in b or b in a


def _ev(**kw) -> Evidence:
    return Evidence(**kw)


def quality_checks(o: Observations) -> list[Evidence]:
    out = []
    for name, q in o.quality.items():
        if not q.get("ok", True):
            out.append(_ev(source=S.S0, rule="Q_quality", polarity=P.down, strength=St.strong, resolvable=True,
                           confidence=0.95, summary=f"图片{('、'.join(q['issues']))}，无法可靠判断",
                           locator={"image": name}, detail={**q, "supplement": "请在光线充足处重新拍摄清晰的破损位置照片"}))
    return out


def x1_pixel(o: Observations) -> list[Evidence]:
    th = thresholds()["pixel"]
    out = []
    for name, px in o.pixel.items():
        if not px:
            continue
        damages = (o.vision.get(name) or {}).get("damages", [])
        aigc, tamper = px.get("aigc", 0), px.get("tamper", 0)
        if aigc >= th["aigc_medium"]:
            strong = aigc >= th["aigc_strong"]
            out.append(_ev(source=S.S1, rule="X1_aigc", polarity=P.down, strength=St.strong if strong else St.medium,
                           confidence=round(aigc, 2), summary=f"整图疑似 AI 生成（概率 {aigc:.2f}）",
                           locator={"image": name, "bbox": px.get("bbox")}, detail={"aigc": aigc}))
        elif tamper >= th["tamper_medium"]:
            bbox = px.get("bbox")
            rel = any(_overlap(bbox, d.get("bbox")) > 0.1 for d in damages) if bbox else True
            region = px.get("region_label") or "局部"
            if rel:
                strong = tamper >= th["tamper_strong"]
                out.append(_ev(source=S.S1, rule="X1_tamper_relevant", polarity=P.down, strength=St.strong if strong else St.medium,
                               confidence=round(tamper, 2), summary=f"{region}存在编辑痕迹（{tamper:.2f}），且与诉求破损部位重叠",
                               locator={"image": name, "bbox": bbox}, detail={"tamper": tamper}))
            else:
                out.append(_ev(source=S.S1, rule="X1_tamper_irrelevant", polarity=P.note, strength=St.weak, claim_relevant=False,
                               confidence=round(tamper, 2), summary=f"{region}有编辑痕迹（如美颜），与诉求部位无关，不计入风险",
                               locator={"image": name, "bbox": bbox}, detail={"tamper": tamper}))
        sus = [p for p in px.get("physics", []) if p.get("suspicious")]
        if sus:
            out.append(_ev(source=S.S1, rule="X1_physics", polarity=P.down, strength=St.medium, confidence=0.7,
                           summary="物理合理性存疑：" + "；".join(f"{p['aspect']}—{p['observation']}" for p in sus),
                           locator={"image": name, "bbox": px.get("bbox")}, detail={"physics": sus}))
    return out


def x2_image_vs_order(o: Observations) -> list[Evidence]:
    if not o.order or not o.product:
        return []
    out = []
    for name, v in o.vision.items():
        if not v:
            continue
        spec = (v.get("spec_text") or "").replace(" ", "").lower()
        if spec and spec != o.order["spec"].lower():
            out.append(_ev(source=S.S2, rule="X2_spec_mismatch", polarity=P.down, strength=St.strong, resolvable=True, confidence=0.85,
                           summary=f"图中规格为 {v['spec_text']}，订单为 {o.order['spec']}", locator={"image": name},
                           detail={"supplement": "请拍摄瓶身规格标识与瓶底批号"}))
        cont = v.get("container")
        if cont and cont != o.product["container"]:
            out.append(_ev(source=S.S2, rule="X2_container_mismatch", polarity=P.down, strength=St.strong, resolvable=True, confidence=0.8,
                           summary=f"图中容器为{CONTAINER_CN.get(cont, cont)}，该商品应为{CONTAINER_CN.get(o.product['container'])}",
                           locator={"image": name}, detail={"supplement": "请拍摄商品正面完整外观及瓶底批号"}))
        batch = v.get("batch_text")
        if batch:
            if batch.upper() == o.order["batch_no"].upper():
                out.append(_ev(source=S.S2, rule="X2_batch_match", polarity=P.up, strength=St.medium, confidence=0.9,
                               summary=f"瓶身批号 {batch} 与发货批次一致", locator={"image": name}))
            else:
                out.append(_ev(source=S.S2, rule="X2_batch_mismatch", polarity=P.down, strength=St.medium, resolvable=True, confidence=0.75,
                               summary=f"瓶身批号 {batch} 与发货批次 {o.order['batch_no']} 不一致", locator={"image": name},
                               detail={"supplement": "请拍摄瓶底批号与外箱快递面单同框"}))
        if spec == o.order["spec"].lower() and (not cont or cont == o.product["container"]):
            out.append(_ev(source=S.S2, rule="X2_match", polarity=P.up, strength=St.weak, confidence=0.8,
                           summary="图中商品规格、包装与订单一致", locator={"image": name}))
    return out


def x3_claim_vs_image(o: Observations) -> list[Evidence]:
    issue = o.claim.issue_type
    if issue not in DAMAGE_ISSUES or not o.vision:
        return []
    out = []
    seen = any(
        any(d.get("type") == issue.value for d in v.get("damages", [])) or (issue == IssueType.leak and v.get("liquid_visible"))
        for v in o.vision.values() if v
    )
    if seen:
        out.append(_ev(source=S.S2, rule="X3_consistent", polarity=P.up, strength=St.medium, confidence=0.8,
                       summary=f"图中可见诉求所述的{ISSUE_CN[issue.value]}"))
    else:
        observed = sorted({ISSUE_CN.get(d.get("type"), "其他") for v in o.vision.values() if v for d in v.get("damages", [])})
        out.append(_ev(source=S.S2, rule="X3_not_visible", polarity=P.down, strength=St.strong, resolvable=True, confidence=0.8,
                       summary=f"诉求为{ISSUE_CN[issue.value]}，图中未见" + (f"（仅见：{'、'.join(observed)}）" if observed else "相关痕迹"),
                       detail={"supplement": f"请近距离拍摄{ISSUE_CN[issue.value]}的具体位置"}))
    return out


def x4_claim_vs_product(o: Observations) -> list[Evidence]:
    if not o.product:
        return []
    out = []
    issue = o.claim.issue_type.value
    if issue in o.product.get("impossible_damage", []):
        out.append(_ev(source=S.S10, rule="X4_impossible", polarity=P.down, strength=St.strong, resolvable=True, confidence=0.85,
                       summary=f"该商品为{CONTAINER_CN.get(o.product['container'])}，通常不会出现「{ISSUE_CN.get(issue, issue)}」",
                       detail={"supplement": "请从侧面近距离拍摄破损处，并拍摄商品整体外观"}))
    expect = o.product.get("liquid", {}).get("color")
    for name, v in o.vision.items():
        if v and v.get("liquid_visible") and v.get("liquid_color") and expect and not _same_color(v["liquid_color"], expect):
            out.append(_ev(source=S.S10, rule="X4_liquid_color", polarity=P.down, strength=St.medium, confidence=0.75,
                           summary=f"图中液体为{v['liquid_color']}，该商品应为{expect}", locator={"image": name}))
    return out


def x5_timeline(o: Observations) -> list[Evidence]:
    out = []
    lg = o.logistics
    signed = parse_time(lg.get("signed_at")) if lg.get("found") else None
    for name, ex in o.exif.items():
        shot = parse_time(ex.get("shot_at"))
        if shot and signed and shot < signed:
            out.append(_ev(source=S.S3, rule="X5_shot_before_sign", polarity=P.down, strength=St.medium, confidence=0.7,
                           summary=f"照片拍摄时间 {ex['shot_at'][:16]} 早于签收时间 {lg['signed_at'][:16]}", locator={"image": name}))
    late = thresholds()["logistics"]["late_report_days"]
    if o.claim.time_hint == "on_arrival" and lg.get("days_after_sign") and lg["days_after_sign"] > late:
        out.append(_ev(source=S.S7, rule="X5_late_report", polarity=P.down, strength=St.medium, confidence=0.65,
                       summary=f"描述为「刚收到即出现问题」，但签收 {lg['days_after_sign']} 天后才申请"))
    return out


def x6_chat(o: Observations) -> list[Evidence]:
    first = o.claim.chat_first_reason
    if first == "non_quality" and o.claim.issue_type not in (IssueType.other,):
        return [_ev(source=S.S5, rule="X6_reason_shift", polarity=P.down, strength=St.medium, confidence=0.7,
                    summary=f"聊天中首次反馈为非质量原因（如不喜欢），售后申请改为「{ISSUE_CN.get(o.claim.issue_type.value)}」")]
    return []


def s7_transit(o: Observations) -> list[Evidence]:
    lg = o.logistics
    if lg.get("anomalies") and o.claim.issue_type in DAMAGE_ISSUES:
        e = lg["anomalies"][0]
        return [_ev(source=S.S7, rule="S7_transit_damage", polarity=P.up, strength=St.strong, confidence=0.9,
                    summary=f"物流轨迹记录异常：「{e['desc']}」（{e['time'][:16]}）")]
    return []


def s8_account(o: Observations) -> list[Evidence]:
    a = o.account
    if not a.get("found"):
        return []
    if a.get("high_refund"):
        return [_ev(source=S.S8, rule="S8_high_refund", polarity=P.down, strength=St.weak, confidence=0.6,
                    summary=f"近 90 天售后 {a['refunds_90d']} 次，其中仅退款 {a['refund_only_90d']} 次（仅作参考，不单独影响结论）")]
    if a.get("loyal"):
        return [_ev(source=S.S8, rule="S8_loyal", polarity=P.up, strength=St.weak, confidence=0.6,
                    summary=f"老会员（VIP{a['vip_level']}，注册 {a['account_years']} 年，近 90 天售后 {a['refunds_90d']} 次）")]
    return []


def s9_dup(o: Observations) -> list[Evidence]:
    out = []
    for h in o.dup.get("image_hits", []):
        if h["same_account"]:
            out.append(_ev(source=S.S9, rule="S9_same_account_reuse", polarity=P.note, strength=St.weak, claim_relevant=False,
                           summary=f"与本账号历史工单 {h['other_ticket']} 使用相同图片", locator={"image": h["image"]}, detail=h))
        elif h["exact"]:
            out.append(_ev(source=S.S9, rule="S9_exact_dup", polarity=P.down, strength=St.strong, confidence=0.95,
                           summary=f"凭证图与其他账号工单 {h['other_ticket']}（{h['other_created_at'][:10]}）的图片几乎相同（距离 {h['distance']}）",
                           locator={"image": h["image"]}, detail=h))
        else:
            out.append(_ev(source=S.S9, rule="S9_near_dup", polarity=P.down, strength=St.medium, confidence=0.7,
                           summary=f"凭证图与工单 {h['other_ticket']} 的图片高度相似（距离 {h['distance']}）",
                           locator={"image": h["image"]}, detail=h))
    for t in o.dup.get("text_hits", []):
        out.append(_ev(source=S.S9, rule="S9_text_template", polarity=P.down, strength=St.weak, confidence=0.6,
                       summary=f"诉求文案与其他账号工单 {t['other_ticket']} 相似度 {t['similarity']}", detail=t))
    return out


def s11_batch(o: Observations) -> list[Evidence]:
    b = o.batch
    if b and b.get("credible_same_issue", 0) >= thresholds()["batch"]["min_credible_same_issue"]:
        return [_ev(source=S.S11, rule="S11_batch_cluster", polarity=P.up, strength=St.strong, confidence=0.85,
                    summary=f"同批次 {b['batch_no']} 近 {b['window_days']} 天已有 {b['credible_same_issue']} 起可信的同类投诉", detail=b)]
    return []


CHECKS = [quality_checks, x1_pixel, x2_image_vs_order, x3_claim_vs_image, x4_claim_vs_product,
          x5_timeline, x6_chat, s7_transit, s8_account, s9_dup, s11_batch]


def run(o: Observations) -> list[Evidence]:
    ev: list[Evidence] = []
    for fn in CHECKS:
        ev.extend(fn(o))
    for i, e in enumerate(ev, 1):
        e.id = f"E{i}"
    return ev
