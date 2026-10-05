"""S0 图像质量闸门 / S3 EXIF / 图像指纹。纯本地计算，零成本。"""
import io
from datetime import datetime
from functools import lru_cache

import imagehash
import numpy as np
from PIL import Image

from ..config import thresholds


def load(b: bytes) -> Image.Image:
    return Image.open(io.BytesIO(b))


def quality(b: bytes) -> dict:
    th = thresholds()["quality"]
    img = load(b)
    w, h = img.size
    g = img.convert("L")
    g.thumbnail((512, 512))
    a = np.asarray(g, dtype=np.float32)
    lap = a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:] - 4 * a[1:-1, 1:-1]
    blur_var = float(lap.var())
    brightness = float(a.mean())
    issues = []
    if blur_var < th["blur_laplacian_var_min"]:
        issues.append("画面模糊")
    if brightness < th["brightness_min"]:
        issues.append("画面过暗")
    if brightness > th["brightness_max"]:
        issues.append("画面过曝")
    if min(w, h) < th["min_side_px"]:
        issues.append("分辨率过低")
    return {"width": w, "height": h, "blur_var": round(blur_var, 1), "brightness": round(brightness, 1),
            "ok": not issues, "issues": issues}


def exif(b: bytes) -> dict:
    img = load(b)
    ex = img.getexif()
    sub = ex.get_ifd(0x8769) if ex else {}
    raw = sub.get(0x9003) or ex.get(0x0132) if ex else None
    shot_at = None
    if raw:
        try:
            shot_at = datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S").isoformat()
        except ValueError:
            shot_at = None
    return {"has_exif": bool(ex), "shot_at": shot_at, "model": ex.get(0x0110) if ex else None,
            "software": ex.get(0x0131) if ex else None}


@lru_cache(maxsize=2048)
def phash_bytes(b: bytes, size: int) -> imagehash.ImageHash:
    return imagehash.phash(load(b).convert("RGB"), hash_size=size)
