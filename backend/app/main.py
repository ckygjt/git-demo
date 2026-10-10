import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from . import eval_summary, orchestrator
from .config import settings, thresholds
from .repo import repo
from .fusion.disposition import ACTION_CN, VERDICT_CN

app = FastAPI(title="TruthGuard · 售后客诉证据鉴真 Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"ok": True, "mode": "mock" if settings().mock else "llm", "providers": [p.name for p in settings().providers]}


@app.get("/api/eval")
def eval_results():
    return {**eval_summary.summary(), "tamper_model_min": thresholds()["pixel"].get("tamper_model_min")}


@app.get("/api/tickets")
def tickets():
    r = repo()
    return [
        {**{k: t[k] for k in ("ticket_id", "case", "type", "reason", "description", "images", "order_id", "account_id", "created_at", "status") if k in t},
         "verdict": r.results.get(t["ticket_id"], {}).get("verdict")}
        for t in r.tickets.values() if t.get("status") == "pending"
    ]


@app.get("/api/tickets/{tid}")
def ticket_detail(tid: str):
    r = repo()
    t = r.ticket(tid)
    if not t:
        raise HTTPException(404, "ticket not found")
    order = r.order(t["order_id"])
    return {"ticket": t, "order": order, "product": r.product(order["sku_id"]) if order else None,
            "logistics": r.logistics.get(t["order_id"]), "chat": r.chats.get(tid), "account": r.accounts.get(t["account_id"])}


@app.get("/api/images/{name}")
def image(name: str):
    p = repo().image_path(name)
    if not p.exists() or p.parent != repo().image_path("x").parent:
        raise HTTPException(404)
    return FileResponse(p)


@app.post("/api/tickets/{tid}/verify")
def verify(tid: str):
    if not repo().ticket(tid):
        raise HTTPException(404, "ticket not found")
    result = None
    for kind, payload in orchestrator.verify(tid):
        if kind == "result":
            result = payload
    return _wrap(result)


@app.get("/api/tickets/{tid}/stream")
def stream(tid: str):
    if not repo().ticket(tid):
        raise HTTPException(404, "ticket not found")

    def gen():
        for kind, payload in orchestrator.verify(tid):
            data = _wrap(payload) if kind == "result" else payload.model_dump(mode="json")
            yield f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


def _wrap(result):
    d = result.model_dump(mode="json")
    d["verdict_cn"] = VERDICT_CN[result.verdict]
    d["action_cn"] = ACTION_CN[result.action]
    return d
