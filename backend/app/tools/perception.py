"""S2 视觉内容理解（VLM，只描述不裁决）与 S1 像素取证。

Mock 模式读取 data/seed/fixtures 回放；真实模式调用 VLM，失败则回退回放。
"""
import json
from functools import lru_cache

from ..config import FIXTURES, thresholds
from ..llm.router import chat_json
from . import forensics_aigc, forensics_tamper

ISSUE_ENUM = {"outer_box_damage", "container_crack", "pump_broken", "leak", "missing_item", "wrong_item", "quality", "other"}
CONTAINER_ENUM = {"glass_bottle", "plastic_bottle", "plastic_tube", "glass_jar", "aluminum_tube", None}

VISION_SYSTEM = """你是美妆电商售后的图像描述员。只描述图中客观可见的内容，不要判断真假或诉求是否成立。
严格输出 JSON：
{"product_category": 品类或null, "container": "glass_bottle|plastic_bottle|plastic_tube|glass_jar|aluminum_tube"或null,
 "closure": "pump|dropper|flip_cap|screw_lid|spray"或null, "spec_text": 瓶身可读规格如"30ml"或null,
 "batch_text": 可读批号或null,
 "damages": [{"type": "outer_box_damage|container_crack|pump_broken|leak|other", "part": 部位, "bbox": [x1,y1,x2,y2] 相对坐标0-1}],
 "liquid_visible": bool, "liquid_color": 颜色或null, "with_waybill": 是否与快递面单同框,
 "item_count": 商品件数或null, "person_present": 是否有人像, "notes": 一句话描述}"""


@lru_cache
def _fixture(name: str) -> dict:
    with open(FIXTURES / name, encoding="utf-8") as f:
        return json.load(f)


def _normalize_vision(d: dict) -> dict:
    d.setdefault("damages", [])
    d["damages"] = [x for x in d["damages"] if isinstance(x, dict)]
    for x in d["damages"]:
        if x.get("type") not in ISSUE_ENUM:
            x["type"] = "other"
    if d.get("container") not in CONTAINER_ENUM:
        d["container"] = None
    d["liquid_visible"] = bool(d.get("liquid_visible"))
    return d


def vision(image_name: str, b: bytes) -> tuple[dict | None, str, dict]:
    data, meta = chat_json("vision", VISION_SYSTEM, "请描述这张售后凭证图。", [b])
    if data is not None:
        return _normalize_vision(data), "llm", meta
    fx = _fixture("vision.json").get(image_name)
    return (_normalize_vision(dict(fx)) if fx else None), "mock", meta


def pixel(image_name: str, b: bytes) -> tuple[dict | None, str]:
    """有回放数据的演示图走回放（占位图不是真实照片）；其余图在模型可用时跑
    Community Forensics（aigc）与 TruFor（tamper，仅限非商业用途，且 < tamper_model_min 记 0）。
    低分不产出证据（见 crosscheck.x1_pixel），不能用于"证明为真"。"""
    fx = _fixture("pixel.json").get(image_name)
    if fx:
        return dict(fx), "mock"
    res = {"aigc": 0, "tamper": 0, "bbox": None, "region_label": None, "physics": []}
    ran = False
    if forensics_aigc.available():
        try:
            res["aigc"] = round(forensics_aigc.predict(b), 4)
            ran = True
        except Exception:  # noqa: BLE001
            pass
    if forensics_tamper.available():
        try:
            r = forensics_tamper.predict(b)
            ran = True
            if r["score"] >= thresholds()["pixel"]["tamper_model_min"]:
                res["tamper"] = round(r["score"], 4)
                bb = r["bbox"]
                if bb and (bb[2] - bb[0]) * (bb[3] - bb[1]) < 0.6:
                    res["bbox"] = bb
        except Exception:  # noqa: BLE001
            pass
    return (res, "model") if ran else (None, "mock")
