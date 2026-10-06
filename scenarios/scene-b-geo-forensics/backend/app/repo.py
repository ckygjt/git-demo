"""案例仓储：上传落盘、案例读写、示例案例。"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .config import CASES, UPLOADS, ensure_dirs, mock_sources
from .schemas import Artifact, VerifyResult


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_upload(data: bytes, filename: str) -> Artifact:
    ensure_dirs()
    digest = sha256(data)
    safe = re.sub(r"[^\w.\-]", "_", filename or "upload")
    name = f"{digest[:12]}_{safe}"
    path = UPLOADS / name
    path.write_bytes(data)

    width = height = 0
    mime = ""
    usable = True
    note = ""
    try:
        from PIL import Image  # 可选依赖

        with Image.open(path) as im:
            width, height = im.size
            mime = im.get_mimetype() if hasattr(im, "get_mimetype") else (im.format or "")
    except Exception:  # noqa: BLE001
        usable = False
        note = "无法解析为图片，已忽略图像取证分支"
    return Artifact(name=name, path=str(path), sha256=digest, width=width, height=height,
                    mime=mime, usable=usable, note=note)


def sample_cases() -> list[dict]:
    return list(mock_sources().get("sample_cases") or [])


def get_sample(case_id: str) -> dict | None:
    return next((c for c in sample_cases() if c.get("id") == case_id), None)


def save_case(result: VerifyResult) -> Path:
    ensure_dirs()
    path = CASES / f"{result.case_id}.json"
    path.write_text(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_case(case_id: str) -> dict | None:
    path = CASES / f"{case_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_cases(limit: int = 50) -> list[dict]:
    ensure_dirs()
    files = sorted(CASES.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    out = []
    for p in files:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        out.append({
            "case_id": d.get("case_id"),
            "brand": (d.get("input") or {}).get("brand"),
            "product": (d.get("input") or {}).get("product"),
            "level_cn": (d.get("verdict") or {}).get("level_cn"),
            "risk_score": (d.get("verdict") or {}).get("risk_score"),
            "mode": d.get("mode"),
            "saved_at": p.stat().st_mtime,
        })
    return out
