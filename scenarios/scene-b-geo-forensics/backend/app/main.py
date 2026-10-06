"""场景B FastAPI 入口：REST + SSE 流式步骤事件 + 静态控制台。"""

from __future__ import annotations

import json
import queue
import random
import string
import time
from pathlib import Path
from threading import Thread
from typing import Iterator

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import CASES, WEB, ensure_dirs, settings, thresholds
from .schemas import (
    Artifact,
    CaseInput,
    EvidenceStatus,
    POLARITY_CN,
    STATUS_CN,
    VerifyResult,
)
from . import orchestrator
from .fusion import disposition, rules
from .repo import load_case, list_cases, sample_cases, save_case
from .tools.registry import WEIGHT_KEY

ensure_dirs()

app = FastAPI(title="美妆 GEO 伪造信源核验 Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def new_case_id() -> str:
    stamp = time.strftime("%Y%m%d%H%M%S")
    return f"case_{stamp}_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=4))


def _input_path(case_id: str) -> Path:
    return CASES / f"{case_id}.input.json"


class OverrideIn(BaseModel):
    kind: str
    value: str
    status: str  # confirmed | contradicted | not_found | unverifiable
    note: str = ""


@app.get("/api/health")
def health():
    s = settings()
    return {"ok": True, "mode": s.effective, "agent_mode": s.mode,
            "has_llm": s.has_llm, "has_search": s.has_search,
            "vision_model": s.vision_model, "timeout": s.timeout}


@app.get("/api/samples")
def samples():
    return sample_cases()


@app.get("/api/cases")
def cases():
    return list_cases()


@app.post("/api/cases")
async def create_case(
    text: str = Form(default=""),
    source_url: str = Form(default=""),
    brand: str = Form(default=""),
    product: str = Form(default=""),
    image_names: str = Form(default=""),
    images: list[UploadFile] = File(default=None),  # type: ignore[assignment]
):
    from .repo import save_upload

    ensure_dirs()
    artifacts = []
    for up in images or []:
        data = await up.read()
        if data:
            artifacts.append(save_upload(data, up.filename or "upload"))
    # 示例案例可声明虚拟素材名（无本地文件，按名称回放）
    for name in [x.strip() for x in (image_names or "").split(",") if x.strip()]:
        artifacts.append(Artifact(name=name, path="", sha256="", usable=True, note="示例素材（按名称回放）"))

    case_id = new_case_id()
    inp = CaseInput(text=text, source_url=source_url, brand=brand, product=product, images=artifacts)
    _input_path(case_id).write_text(inp.model_dump_json(), encoding="utf-8")
    return {"case_id": case_id, "input": inp.model_dump(mode="json")}


def _load_input(case_id: str) -> CaseInput:
    p = _input_path(case_id)
    if not p.exists():
        raise HTTPException(404, "case not found")
    return CaseInput(**json.loads(p.read_text(encoding="utf-8")))


@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    d = load_case(case_id)
    return d if d else {"case_id": case_id, "status": "pending"}


def _iter_events(case_id: str) -> Iterator[str]:
    inp = _load_input(case_id)
    q: queue.Queue = queue.Queue()

    def worker() -> None:
        try:
            for kind, payload in orchestrator.verify(inp, case_id):
                q.put((kind, payload))
        except Exception as e:  # noqa: BLE001
            q.put(("error", {"message": f"{type(e).__name__}: {e}"}))
        finally:
            q.put(("__end__", None))

    Thread(target=worker, daemon=True).start()

    while True:
        try:
            kind, payload = q.get(timeout=15)
        except queue.Empty:
            yield ": heartbeat\n\n"
            continue
        if kind == "__end__":
            break
        if kind == "error":
            yield f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            break
        data = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
        yield f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    yield "event: end\ndata: {}\n\n"


@app.get("/api/cases/{case_id}/stream")
def stream_case(case_id: str):
    if not _input_path(case_id).exists():
        raise HTTPException(404, "case not found")
    return StreamingResponse(_iter_events(case_id), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/cases/{case_id}/override")
def override(case_id: str, body: OverrideIn):
    d = load_case(case_id)
    if not d:
        raise HTTPException(404, "case not found，请先完成一次核验")

    try:
        status = EvidenceStatus(body.status)
    except ValueError as e:
        raise HTTPException(400, f"非法状态：{body.status}") from e

    thr = thresholds()
    hit = None
    for e in d.get("evidences", []):
        if e.get("kind") == body.kind and e.get("query") == body.value:
            hit = e
            break
    if hit is None:
        raise HTTPException(404, "未找到对应证据条目")

    weight_key = WEIGHT_KEY.get((body.kind, status), "")
    weight = float(thr.get("weights", {}).get(weight_key, 0.0))
    hit["status"] = status.value
    hit["status_cn"] = STATUS_CN.get(status, status.value)
    hit["weight"] = weight
    hit["polarity"] = "up" if weight > 0 else ("down" if weight < 0 else "note")
    hit["polarity_cn"] = POLARITY_CN.get(hit["polarity"], "")
    hit["needs_human_review"] = False
    hit["summary"] = f"{hit.get('summary', '')}（人工覆盖为「{hit['status_cn']}」{('：' + body.note) if body.note else ''}）"

    result = VerifyResult(**d)
    verdict = rules.fuse(result.evidences, result.findings, thr)
    result.verdict = verdict
    result.action = disposition.ACTION_OF[verdict.level]
    result.action_cn = disposition.ACTION_CN[result.action]
    result.missing_materials = disposition.supplement_requests(result.evidences)
    result.script = disposition.script(result.action, result.missing_materials, verdict.fired_redline)
    save_case(result)
    return result.model_dump(mode="json")


def _to_markdown(r: VerifyResult) -> str:
    v = r.verdict
    lines = [
        f"# GEO 伪造信源核验报告 · {r.case_id}",
        "",
        f"- 运行模式：{'真实 API' if r.mode == 'real' else 'Mock 演示'}",
        f"- 品牌/产品：{r.input.brand or '-'} / {r.input.product or '-'}",
        f"- 来源：{r.input.source_url or '-'}",
        f"- 结论：**{v.level_cn if v else '-'}**（风险分 {v.risk_score if v else '-'}，置信度 {v.confidence if v else '-'}）",
        f"- 依据：{v.reason if v else '-'}",
        f"- 处置：{r.action_cn}",
        "",
        "## 一、主张抽取",
    ]
    lines += [f"- [{c.type_cn or c.type}] {c.text}（实体：{'、'.join(c.entities) or '无'}）" for c in r.claims] or ["- 无"]
    lines += ["", "## 二、证据链"]
    for e in r.evidences:
        lines.append(f"- **{e.tool_cn or e.tool}** `{e.query}` → {e.status_cn}／{e.polarity_cn}{e.weight:+.0f}：{e.summary}"
                     + (f"（来源：{e.source_url}）" if e.source_url else "")
                     + (" [需人工复核]" if e.needs_human_review else ""))
    lines += ["", "## 三、一致性与合规"]
    lines += [f"- {f.dimension}：{'通过' if f.ok else '不通过'}（{f.severity}）— {f.detail}" for f in r.findings] or ["- 无"]
    lines += ["", "## 四、缺失材料清单"]
    lines += [f"- {m}" for m in r.missing_materials] or ["- 无"]
    lines += ["", "## 五、处置话术", "", r.script, "", "> " + r.disclaimer]
    return "\n".join(lines)


@app.get("/api/cases/{case_id}/export")
def export_case(case_id: str, format: str = "json"):
    d = load_case(case_id)
    if not d:
        raise HTTPException(404, "case not found")
    r = VerifyResult(**d)
    if format.lower() in ("md", "markdown"):
        return PlainTextResponse(_to_markdown(r), media_type="text/markdown; charset=utf-8",
                                 headers={"Content-Disposition": f'attachment; filename="{case_id}.md"'})
    return r.model_dump(mode="json")


if WEB.exists():
    app.mount("/", StaticFiles(directory=str(WEB), html=True), name="web")
