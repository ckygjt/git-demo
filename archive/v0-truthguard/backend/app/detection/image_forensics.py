"""图像取证引擎（硬证据）：ELA 误差分析 + 噪声一致性 + EXIF/元数据检查。

全部为本地计算，不依赖 GPU 与网络，可在无 API Key 环境独立出报告。
"""
from __future__ import annotations

import base64
import io
import re

import cv2
import numpy as np
from PIL import Image, ExifTags

from .. import config
from ..schemas import Evidence, ImageAnalysis

EDITING_SOFTWARE = r"photoshop|gimp|lightroom|美图|meitu|faceapp|snapseed|canva|adobe|picsart"
AIGC_MARKER = (
    r"stable\s*diffusion|midjourney|comfyui|dall[- ]?e|novelai|invokeai|"
    r"sd[-_ ]?xl|a1111|automatic1111|flux|generated\s*by|ai\s*generated"
)


def _clamp01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def load_image(data: bytes) -> Image.Image:
    """读入图像并统一缩放到最长边 MAX_EDGE，避免大图阻塞。"""
    img = Image.open(io.BytesIO(data))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    w, h = img.size
    scale = config.MAX_EDGE / max(w, h)
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return img


def _to_bgr(img: Image.Image) -> np.ndarray:
    arr = np.asarray(img.convert("RGB"))
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def _block_grid(arr: np.ndarray, grid: int = 16) -> np.ndarray:
    """把二维图切成 grid×grid 块，返回每块的均值矩阵。"""
    h, w = arr.shape
    bh, bw = max(1, h // grid), max(1, w // grid)
    blocks = arr[: bh * grid, : bw * grid].reshape(grid, bh, grid, bw)
    return blocks.mean(axis=(1, 3))


# ---------------- ELA 误差级别分析 ----------------
def ela_map(img: Image.Image, quality: int = 90) -> np.ndarray:
    """重压缩后与原图求差，篡改区域误差显著更高。"""
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=quality)
    buf.seek(0)
    rec = Image.open(buf).convert("RGB")
    diff = np.abs(
        np.asarray(img.convert("RGB"), dtype=np.float32)
        - np.asarray(rec, dtype=np.float32)
    )
    return diff.mean(axis=2)


def _ela_score(emap: np.ndarray) -> tuple[float, list[float] | None]:
    grid = _block_grid(emap)
    p50, p95 = float(np.percentile(grid, 50)), float(np.percentile(grid, 95))
    # 局部对比度：p95 远高于 p50 说明存在异常高误差区域
    contrast = (p95 - p50) / 12.0
    score = _clamp01(contrast)

    thr = p50 + max(2.0, (p95 - p50) * 0.6)
    mask = grid >= thr
    region = None
    if mask.sum() >= 2 and mask.sum() < grid.size * 0.6:
        ys, xs = np.where(mask)
        g = grid.shape[0]
        x0, x1 = xs.min() / g, (xs.max() + 1) / g
        y0, y1 = ys.min() / g, (ys.max() + 1) / g
        region = [round(float(x0), 3), round(float(y0), 3),
                  round(float(x1 - x0), 3), round(float(y1 - y0), 3)]
    return score, region


# ---------------- 噪声一致性 ----------------
def _noise_score(bgr: np.ndarray) -> tuple[float, np.ndarray]:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    noise = cv2.absdiff(gray, cv2.medianBlur(gray, 5)).astype(np.float32)
    stds = _block_grid(noise)
    mean = float(stds.mean())
    p10, p90 = float(np.percentile(stds, 10)), float(np.percentile(stds, 90))
    if mean < 1e-6:
        return 0.0, noise
    dispersion = (p90 - p10) / mean  # 均匀噪声≈1~1.5，拼接区域显著更高
    return _clamp01((dispersion - 1.4) / 2.2), noise


# ---------------- 元数据 / EXIF ----------------
def _metadata_check(img: Image.Image) -> tuple[float, list[str]]:
    score, findings = 0.0, []
    try:
        exif = img.getexif() or {}
    except Exception:
        exif = {}
    tags = {ExifTags.TAGS.get(k, str(k)): v for k, v in exif.items()}
    blob = " ".join(str(v) for v in tags.values()).lower()
    blob += " " + " ".join(f"{k}:{v}" for k, v in (img.info or {}).items()).lower()

    fmt = (img.format or "").upper()

    if fmt == "JPEG" and not tags:
        score += 0.25
        findings.append("JPEG 图像缺少 EXIF 拍摄参数，通常经过二次导出或编辑")

    if re.search(EDITING_SOFTWARE, blob):
        score += 0.5
        findings.append("元数据中检测到图像编辑软件痕迹，图片很可能被后期处理")

    if re.search(AIGC_MARKER, blob):
        score += 0.9
        findings.append("元数据中检测到 AI 生成工具标记，高度疑似 AIGC 合成图")

    if fmt == "PNG" and any(k.lower() in ("parameters", "comment", "description")
                            for k in (img.info or {})):
        score += 0.15
        findings.append("PNG 内嵌文本块含生成参数，常见于导出型合成图")

    if not findings:
        findings.append("元数据未发现明显编辑或生成痕迹")
    return _clamp01(score), findings


def _heatmap(img: Image.Image, emap: np.ndarray) -> str:
    """生成 ELA 热力图（青→黄→红）叠加原图，返回 base64 PNG。"""
    norm = cv2.normalize(emap, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    color = cv2.applyColorMap(norm, cv2.COLORMAP_JET)
    color = cv2.cvtColor(color, cv2.COLOR_BGR2RGB)
    base = np.asarray(img.convert("RGB"))
    if color.shape != base.shape:
        color = cv2.resize(color, (base.shape[1], base.shape[0]))
    overlay = cv2.addWeighted(base, 0.55, color, 0.45, 0)
    # 输出 JPEG（质量 82）并限制尺寸，避免 base64 过大拖慢接口响应
    h, w = overlay.shape[:2]
    scale = 768 / max(h, w)
    if scale < 1.0:
        overlay = cv2.resize(overlay, (int(w * scale), int(h * scale)), cv2.INTER_AREA)
    ok, buf = cv2.imencode(
        ".jpg", cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR), [int(cv2.IMWRITE_JPEG_QUALITY), 82]
    )
    if not ok:
        return ""
    return base64.b64encode(buf.tobytes()).decode()


def analyze(data: bytes) -> ImageAnalysis:
    """图像取证主入口：返回证据列表、热力图与综合分数。"""
    img = load_image(data)
    bgr = _to_bgr(img)

    emap = ela_map(img)
    ela_score, region = _ela_score(emap)
    noise_s, _ = _noise_score(bgr)
    meta_s, findings = _metadata_check(img)

    evidence = [
        Evidence(
            source="forensics",
            name="ELA 误差级别分析",
            score=round(ela_score, 3),
            weight=config.EVIDENCE_WEIGHT["ela"],
            description=(
                f"重压缩误差分布不均，局部异常区域置信度 {ela_score:.2f}"
                if ela_score >= 0.35
                else f"重压缩误差分布均匀，未发现明显二次编辑痕迹（{ela_score:.2f}）"
            ),
            region=region,
            severity="high" if ela_score >= 0.6 else "medium" if ela_score >= 0.35 else "low",
        ),
        Evidence(
            source="forensics",
            name="噪声一致性分析",
            score=round(noise_s, 3),
            weight=config.EVIDENCE_WEIGHT["noise"],
            description=(
                f"分块噪声方差离散，疑似存在拼接或外来区域（{noise_s:.2f}）"
                if noise_s >= 0.35
                else f"全图噪声特征一致，未见拼接痕迹（{noise_s:.2f}）"
            ),
            severity="high" if noise_s >= 0.6 else "medium" if noise_s >= 0.35 else "low",
        ),
        Evidence(
            source="forensics",
            name="EXIF / 元数据检查",
            score=round(meta_s, 3),
            weight=config.EVIDENCE_WEIGHT["metadata"],
            description="；".join(findings[:2]),
            severity="high" if meta_s >= 0.6 else "medium" if meta_s >= 0.35 else "low",
        ),
    ]

    blend = config.IMAGE_BLEND
    image_score = 100.0 * (
        blend["ela"] * ela_score + blend["noise"] * noise_s + blend["metadata"] * meta_s
    )

    return ImageAnalysis(
        width=img.width,
        height=img.height,
        format=img.format or "UNKNOWN",
        heatmap=_heatmap(img, emap),
        evidence=evidence,
        findings=findings,
        image_score=round(image_score, 2),
    )
