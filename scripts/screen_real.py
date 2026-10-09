"""用 VLM 复核真实候选图：是否是美妆/个护产品包装、是否有可见的包装破损/漏液、是否含人脸等隐私。

输入: data/seed/real_candidates.jsonl（声称破损）、data/seed/real_intact.jsonl（好评晒图）
输出: data/seed/real_screened.jsonl（每张图的复核结果 + 是否入选）
结果由 router 磁盘缓存，重复运行不重复计费。

用法: python scripts/screen_real.py [--workers 4] [--limit N]
"""
import argparse
import io
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.llm.router import chat_json  # noqa: E402

SYSTEM = "你是电商售后图片审核员，只输出 JSON，不要解释。"
PROMPT = """判断这张买家上传的图片，输出 JSON：
{"is_package": 画面主体是否为化妆品/护肤品/个护产品的瓶罐管盒等包装（布尔）,
 "container": "glass_bottle|plastic_bottle|tube|jar|box|compact|other|none",
 "visible_damage": 包装上是否有肉眼可见的破损/漏液/压扁/裂纹/断裂（布尔）,
 "damage_type": "leak|crack|crushed_box|broken_part|none",
 "has_face_or_skin": 画面是否含人脸或大面积人体皮肤（布尔）,
 "has_brand_text": 是否有清晰可读的品牌文字（布尔）,
 "quality": "good|ok|poor"}"""


def prep(path: Path) -> bytes:
    im = Image.open(path).convert("RGB")
    im.thumbnail((640, 640))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=85)
    return b.getvalue()


def screen(row: dict):
    p = ROOT / "data" / "images" / row["file"]
    try:
        data, meta = chat_json("vision", SYSTEM, PROMPT, [prep(p)])
    except Exception as e:  # noqa: BLE001
        return {**row, "error": type(e).__name__}
    if not data:
        return {**row, "error": "no_result", "meta_errors": meta["errors"]}
    row = {k: row[k] for k in ("file", "review_key", "rating", "truth", "text") if k in row}
    keep = bool(data.get("is_package")) and not data.get("has_face_or_skin") and data.get("quality") != "poor"
    if row["truth"] == "real_claimed_damage":
        keep = keep and bool(data.get("visible_damage"))
    else:
        keep = keep and not data.get("visible_damage")
    return {**row, **data, "keep": keep, "tokens_in": meta["tokens_in"], "cached": meta["cached"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")

    rows = []
    for name in ("real_candidates", "real_intact"):
        f = ROOT / "data" / "seed" / f"{name}.jsonl"
        if f.exists():
            rows += [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l]
    if args.limit:
        rows = rows[: args.limit]
    print(f"待复核 {len(rows)} 张")

    with ThreadPoolExecutor(args.workers) as ex:
        res = list(ex.map(screen, rows))

    out = ROOT / "data" / "seed" / "real_screened.jsonl"
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in res) + "\n", encoding="utf-8")
    err = [r for r in res if "error" in r]
    ok = [r for r in res if r.get("keep")]
    for t in ("real_claimed_damage", "real_intact"):
        sub = [r for r in res if r.get("truth") == t]
        print(f"{t}: 共 {len(sub)}，入选 {sum(1 for r in sub if r.get('keep'))}")
    print(f"失败 {len(err)}，累计输入 token {sum(r.get('tokens_in', 0) for r in res if not r.get('cached'))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
