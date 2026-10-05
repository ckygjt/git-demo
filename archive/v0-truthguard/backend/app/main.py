"""真鉴 TruthGuard 后端服务入口。

启动：uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from . import config
from .agent.risk_agent import decide
from .detection import image_forensics, llm_vision, text_detector
from .schemas import HealthResponse, ImageAnalysis, RiskReport, TextAnalysis, TextRequest

app = FastAPI(
    title="真鉴 TruthGuard",
    description="美妆内容多模态鉴真与风控 Agent",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_BYTES = config.MAX_UPLOAD_MB * 1024 * 1024


def _read_sync(upload: UploadFile) -> bytes:
    return upload.file.read()


async def _load_upload(upload: UploadFile) -> tuple[bytes, str]:
    data = await run_in_threadpool(_read_sync, upload)
    if not data:
        raise HTTPException(status_code=400, detail="上传文件为空")
    if len(data) > MAX_BYTES:
        raise HTTPException(
            status_code=413, detail=f"文件超过 {config.MAX_UPLOAD_MB}MB 限制"
        )
    return data, upload.content_type or "image/jpeg"


def _analyze_image(data: bytes, mime: str) -> ImageAnalysis:
    result = image_forensics.analyze(data)
    vision = llm_vision.analyze(data, mime)
    if vision is not None:
        result.evidence.append(vision)
    return result


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        llm_provider=config.LLM_PROVIDER or "none",
        llm_enabled=config.ENABLE_LLM,
        vision_enabled=config.VISION_ENABLED,
    )


@app.post("/api/detect/image", response_model=RiskReport)
async def detect_image(file: UploadFile = File(...)) -> RiskReport:
    data, mime = await _load_upload(file)
    image = await run_in_threadpool(_analyze_image, data, mime)
    return await run_in_threadpool(decide, image, None)


@app.post("/api/detect/text", response_model=RiskReport)
async def detect_text(req: TextRequest) -> RiskReport:
    text = await run_in_threadpool(text_detector.analyze, req.text)
    return await run_in_threadpool(decide, None, text)


@app.post("/api/detect/full", response_model=RiskReport)
async def detect_full(
    file: UploadFile | None = File(None),
    text: str = Form(""),
) -> RiskReport:
    """演示主接口：图文联合检测，任一为空则只跑对应通道。"""
    image: ImageAnalysis | None = None
    text_result: TextAnalysis | None = None

    if file is not None:
        data, mime = await _load_upload(file)
        image = await run_in_threadpool(_analyze_image, data, mime)
    if text.strip():
        text_result = await run_in_threadpool(text_detector.analyze, text.strip())

    if image is None and text_result is None:
        raise HTTPException(status_code=400, detail="请至少提供图片或文案")

    return await run_in_threadpool(decide, image, text_result)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=config.BACKEND_PORT)
