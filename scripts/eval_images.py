"""图像层评测：真实破损 / 真实完好 / AI 假破损 三类图，各跑两项测量。

A. 损伤识别：perception.vision 是否报出 damages（真实破损应报出，完好不应报出）
B. 零样本 AI 判别（基线）：直接让 VLM 判断是否 AI 生成，量化"为何需要像素取证"

公平性：所有图统一缩放到最长边 768 并重编码为 JPEG q85，避免格式/分辨率泄漏。
结果由 router 磁盘缓存；输出 data/eval/image_eval.json。

用法: python scripts/eval_images.py [--workers 2] [--per-set 0]
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
from app.tools import perception  # noqa: E402

AI_SYSTEM = "你是图像取证分析员，只输出 JSON。"
AI_PROMPT = """这是一张买家为'仅退款'售后上传的商品破损凭证图。判断它是否可能是 AI 生成或 AI 编辑的。
输出 JSON: {"ai_generated_prob": 0到1的小数, "reasons": ["最多3条简短依据"]}"""


def norm(path: Path) -> bytes:
    im = Image.open(path).convert("RGB")
    im.thumbnail((768, 768))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=85)
    return b.getvalue()


def load_sets(per_set: int) -> dict[str, list[Path]]:
    seed = ROOT / "data" / "seed"
    img = ROOT / "data" / "images"
    screened = [json.loads(l) for l in (seed / "real_screened.jsonl").read_text(encoding="utf-8").splitlines() if l]
    sets = {
        "real_damaged": [img / r["file"] for r in screened if r.get("keep") and r["truth"] == "real_claimed_damage"],
        "real_intact": [img / r["file"] for r in screened if r.get("keep") and r["truth"] == "real_intact"],
        "fake_damaged": [img / json.loads(l)["file"] for l in (seed / "gen_manifest.jsonl").read_text(encoding="utf-8").splitlines() if l],
    }
    sets["fake_damaged"] = [p for p in sets["fake_damaged"] if p.exists()]
    if per_set:
        sets = {k: v[:per_set] for k, v in sets.items()}
    return sets


def measure(item: tuple[str, Path]) -> dict:
    label, p = item
    b = norm(p)
    row = {"set": label, "file": p.name}
    try:
        v, mode, meta = perception.vision(p.name, b)
        dm = (v or {}).get("damages", [])
        row.update(vision_ok=v is not None and mode == "llm", n_damages=len(dm), damage_types=[d["type"] for d in dm])
    except Exception as e:  # noqa: BLE001
        row.update(vision_ok=False, vision_error=type(e).__name__)
    try:
        d, meta = chat_json("vision", AI_SYSTEM, AI_PROMPT, [b])
        row.update(ai_prob=float(d["ai_generated_prob"]) if d else None, ai_reasons=(d or {}).get("reasons", []))
    except Exception as e:  # noqa: BLE001
        row.update(ai_prob=None, ai_error=type(e).__name__)
    return row


def rate(rows, key) -> str:
    ok = [r for r in rows if key(r) is not None]
    return f"{sum(1 for r in ok if key(r))}/{len(ok)}" + (f" = {sum(1 for r in ok if key(r)) / len(ok):.0%}" if ok else "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--per-set", type=int, default=0)
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")

    sets = load_sets(args.per_set)
    items = [(k, p) for k, v in sets.items() for p in v]
    print({k: len(v) for k, v in sets.items()})
    with ThreadPoolExecutor(args.workers) as ex:
        rows = list(ex.map(measure, items))

    out = ROOT / "data" / "eval"
    out.mkdir(parents=True, exist_ok=True)
    (out / "image_eval.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n[A] 损伤识别（报出 ≥1 处破损的比例）")
    for k in sets:
        rs = [r for r in rows if r["set"] == k and r.get("vision_ok")]
        print(f"  {k:13s} {rate(rs, lambda r: r['n_damages'] > 0)}")
    print("\n[B] 零样本 AI 判别（ai_prob ≥ 0.5 记为'判为AI'）")
    for k in sets:
        rs = [r for r in rows if r["set"] == k]
        print(f"  {k:13s} {rate(rs, lambda r: None if r.get('ai_prob') is None else r['ai_prob'] >= 0.5)}")
    fails = [r for r in rows if not r.get("vision_ok") or r.get("ai_prob") is None]
    print(f"\n有失败项的图 {len(fails)} 张（可重跑，已成功的走缓存）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
