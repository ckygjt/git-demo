"""Agent 编排器：Step0~7，以生成器产出步骤事件，最后产出 VerifyResult。

约定：yield ("event", StepEvent) ... 最后 yield ("result", VerifyResult)。
"""
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Iterator

from .config import settings
from .fusion import crosscheck, disposition, rules
from .repo import repo
from .schemas import ClaimInfo, IssueType, Polarity, SOURCE_LABEL, StepEvent, ToolOutput, VerifyResult
from .tools import business, claim as claim_tool, image as imgtool, perception

PLAN = {
    IssueType.leak: ["S1 像素取证（液体区域）", "S2 图像内容（液体性状）", "S10 产品知识（液体颜色/可能性）", "S6 订单比对", "S7 物流轨迹", "S9 跨工单", "S11 批次投诉"],
    IssueType.container_crack: ["S1 像素取证", "S2 破损形态", "S10 易损部位与可能性", "S6 订单比对", "S7 物流轨迹", "S9 跨工单"],
    IssueType.pump_broken: ["S1 像素取证", "S2 破损形态", "S10 易损部位与可能性", "S6 订单比对", "S9 跨工单"],
    IssueType.outer_box_damage: ["S2 外盒形态", "S7 轨迹异常", "S6 订单比对", "S9 跨工单", "S11 线路/批次"],
    IssueType.wrong_item: ["S2 品名规格批号", "S6 订单比对"],
    IssueType.missing_item: ["S6 订单件数", "S2 件数"],
}
DEFAULT_PLAN = ["S1 像素取证", "S2 图像内容", "S6 订单比对", "S9 跨工单"]


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


def _timed(fn, *a):
    t0 = time.perf_counter()
    try:
        return fn(*a), None, _ms(t0)
    except Exception as e:  # noqa: BLE001 —— 工具失败只降级，不中断
        return None, f"{type(e).__name__}: {e}", _ms(t0)


def verify(ticket_id: str) -> Iterator[tuple[str, object]]:
    t_start = time.perf_counter()
    r = repo()
    ticket = r.ticket(ticket_id)
    if not ticket:
        raise KeyError(ticket_id)
    mode = "mock" if settings().mock else "llm"

    # Step0 预处理
    t0 = time.perf_counter()
    yield "event", StepEvent(step="s0", title="预处理", status="running")
    images = {n: r.image_path(n).read_bytes() for n in ticket["images"] if r.image_path(n).exists()}
    quality = {n: imgtool.quality(b) for n, b in images.items()}
    exif = {n: imgtool.exif(b) for n, b in images.items()}
    yield "event", StepEvent(step="s0", title="预处理", status="done", elapsed_ms=_ms(t0),
                             detail=f"{len(images)} 张凭证图；" + ("质量合格" if all(q["ok"] for q in quality.values()) else "；".join(f"{n}:{'、'.join(q['issues'])}" for n, q in quality.items() if not q["ok"])),
                             data={"quality": quality})

    # Step1 诉求理解
    t0 = time.perf_counter()
    claim: ClaimInfo = claim_tool.parse(ticket, r.chats.get(ticket_id))
    yield "event", StepEvent(step="s1", title="诉求理解", status="done", elapsed_ms=_ms(t0),
                             detail=f"诉求类型：{crosscheck.ISSUE_CN.get(claim.issue_type.value, claim.issue_type.value)}"
                                    + ("；健康类诉求" if claim.is_health_claim else ""),
                             data=claim.model_dump(mode="json"))

    order = r.order(ticket["order_id"])
    product = r.product(order["sku_id"]) if order else None
    obs = crosscheck.Observations(ticket=ticket, claim=claim, order=order, product=product, quality=quality, exif=exif)
    tools: list[ToolOutput] = []

    if claim.is_health_claim:
        yield "event", StepEvent(step="s2", title="核验规划", status="done", detail="健康安全类：跳过防骗核验，仅整理凭证并转专人")
        plan = ["健康安全类：转专人跟进"]
    else:
        plan = PLAN.get(claim.issue_type, DEFAULT_PLAN)
        yield "event", StepEvent(step="s2", title="核验规划", status="done",
                                 detail=f"诉求为「{crosscheck.ISSUE_CN.get(claim.issue_type.value)}」，计划核验：" + "、".join(plan), data={"plan": plan})

        # Step3 工具并行
        yield "event", StepEvent(step="s3", title="工具并行执行", status="running")
        t0 = time.perf_counter()
        jobs = {
            "S2": lambda: {n: perception.vision(n, b) for n, b in images.items()},
            "S1": lambda: {n: perception.pixel(n, b) for n, b in images.items()},
            "S7": lambda: business.logistics(r, ticket, order),
            "S8": lambda: business.account(r, ticket["account_id"], ticket["created_at"]),
            "S9": lambda: business.cross_ticket(r, ticket, images),
            "S11": lambda: business.batch_cluster(r, ticket, order, claim.issue_type.value) if order else {},
        }
        with ThreadPoolExecutor(max_workers=6) as ex:
            futs = {k: ex.submit(_timed, fn) for k, fn in jobs.items()}
            done = {k: f.result() for k, f in futs.items()}
        errors = 0
        cost = {"tokens_in": 0, "tokens_out": 0, "provider": None, "cached": 0}
        for k, (val, err, ms) in done.items():
            if err:
                errors += 1
            if k == "S1" and val:
                tool_mode = "model" if any(m == "model" for _, m in val.values()) else "mock"
            else:
                tool_mode = mode if k in ("S1", "S2") else "local"
            tools.append(ToolOutput(tool=k, source=k, ok=err is None, error=err, elapsed_ms=ms, mode=tool_mode))
            yield "event", StepEvent(step=f"tool_{k}", title=f"{k} {SOURCE_LABEL[k]}", status="error" if err else "done", elapsed_ms=ms, detail=err or "")
        v_res = done["S2"][0] or {}
        p_res = done["S1"][0] or {}
        for n, (data, m, meta) in v_res.items():
            obs.vision[n] = data
            cost["tokens_in"] += meta.get("tokens_in", 0)
            cost["tokens_out"] += meta.get("tokens_out", 0)
            cost["cached"] += int(meta.get("cached", False))
            cost["provider"] = meta.get("provider")
        for n, (data, m) in p_res.items():
            obs.pixel[n] = data
        obs.logistics = done["S7"][0] or {}
        obs.account = done["S8"][0] or {}
        obs.dup = done["S9"][0] or {}
        obs.batch = done["S11"][0] or {}
        yield "event", StepEvent(step="s3", title="工具并行执行", status="done", elapsed_ms=_ms(t0), detail=f"{len(jobs)} 个工具，{errors} 个失败")
        tool_errors = errors

    if claim.is_health_claim:
        tool_errors, cost = 0, {}

    # Step4 交叉验证
    t0 = time.perf_counter()
    ev = crosscheck.run(obs)
    yield "event", StepEvent(step="s4", title="交叉验证", status="done", elapsed_ms=_ms(t0),
                             detail=f"产出 {len(ev)} 条证据（降信 {sum(e.polarity == Polarity.down for e in ev)}，增信 {sum(e.polarity == Polarity.up for e in ev)}）",
                             data={"evidence": [e.model_dump(mode="json") for e in ev]})

    # Step5 裁决
    verdict, fired, reason, conf = rules.decide(ev, claim.is_health_claim, tool_errors)
    yield "event", StepEvent(step="s5", title="证据融合与裁决", status="done", detail=f"{disposition.VERDICT_CN[verdict]}（规则 {fired}）：{reason}",
                             data={"verdict": verdict.value, "rule": fired})

    # Step6 处置
    action = disposition.ACTION_OF[verdict]
    asks = disposition.supplement_requests(ev) if verdict.value.startswith("doubtful") else []
    script = disposition.script(action, asks)
    yield "event", StepEvent(step="s6", title="处置建议与话术", status="done", detail=disposition.ACTION_CN[action])

    flags = [e for e in ev if e.polarity == Polarity.note or e.strength.value == "weak"]
    main_ev = [e for e in ev if e not in flags]
    result = VerifyResult(
        ticket_id=ticket_id, verdict=verdict, action=action, fired_rule=fired, reason=reason, confidence=conf, claim=claim, plan=plan,
        evidence=main_ev, flags=flags, supplement_requests=asks, script=script, tools=tools, mode=mode, cost=cost if not claim.is_health_claim else {},
        elapsed_ms=_ms(t_start),
    )

    # Step7 写回
    r.save_result(ticket_id, {"verdict": verdict.value, "issue_type": claim.issue_type.value})
    yield "event", StepEvent(step="s7", title="写回跨工单库与批次聚合", status="done")
    yield "result", result
