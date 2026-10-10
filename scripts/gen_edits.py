"""用生图模型的 edits 接口对"真实完好图"局部改出破损，造局部篡改评测样本（仅用于评测）。

每张底图产出两种样本：
  full    API 整图输出（整图被重绘）
  splice  仅把编辑结果的一个局部方框羽化贴回原图，其余像素保持原图（真正的局部拼接）
图存 data/images/edit/，标签写入 data/seed/edit_manifest.jsonl。已存在的跳过，可随时中断后续跑。

用法:
  python scripts/gen_edits.py --dry-run
  python scripts/gen_edits.py --limit 2
"""
import argparse
import base64
import io
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageChops, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "data" / "images"
OUT = IMG / "edit"
MANIFEST = ROOT / "data" / "seed" / "edit_manifest.jsonl"
load_dotenv(ROOT / ".env")

SIZE = 1024
DAMAGES = [
    "a visible crack across the bottle or container body",
    "liquid leaking out and pooling around the bottom of the product, making the surface wet",
    "the cap or pump head snapped off and tilted at an odd angle",
    "the cardboard box crushed and torn at one corner",
]
PROMPT = ("Edit this casual customer photo: make the product look damaged — {d}. "
          "Keep the scene, camera angle, lighting and everything else exactly the same; only change the damaged area. "
          "No added text or logos.")


def square(path: Path) -> Image.Image:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    s = min(w, h)
    im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
    return im.resize((SIZE, SIZE), Image.LANCZOS)


def splice(base: Image.Image, edited: Image.Image) -> tuple[Image.Image, list[float] | None]:
    """只把真正被编辑的区域（按像素差异）羽化贴回原图，其余像素保持原图。"""
    diff = ImageChops.difference(base, edited).convert("L").filter(ImageFilter.GaussianBlur(4))
    mask = diff.point(lambda v: 255 if v > 28 else 0)
    mask = mask.filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.GaussianBlur(8))
    bbox = mask.point(lambda v: 255 if v > 40 else 0).getbbox()
    if bbox is None:
        return base.copy(), None
    out = Image.composite(edited, base, mask)
    return out, [bbox[0] / SIZE, bbox[1] / SIZE, bbox[2] / SIZE, bbox[3] / SIZE]


def bases() -> list[Path]:
    seed = ROOT / "data" / "seed" / "real_screened.jsonl"
    rows = [json.loads(l) for l in seed.read_text(encoding="utf-8").splitlines() if l]
    return [IMG / r["file"] for r in rows if r.get("keep") and r["truth"] == "real_intact"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rebuild-splice", action="store_true", help="不调 API，用已保存的 base/full 重建 splice 与 manifest")
    args = ap.parse_args()

    if args.rebuild_splice:
        rows = []
        for f in sorted(OUT.glob("*__full.png")):
            stem = f.name.split("__")[0]
            base = Image.open(OUT / f"{stem}__base.png").convert("RGB")
            sp, box = splice(base, Image.open(f).convert("RGB"))
            sp.save(OUT / f"{stem}__splice.png")
            rows.append((stem, box))
            print(stem, box)
        old = [json.loads(l) for l in MANIFEST.read_text(encoding="utf-8").splitlines() if l]
        boxes = dict(rows)
        for r in old:
            if r["kind"] == "splice":
                r["box"] = boxes.get(r["file"].split("/")[1].split("__")[0])
        MANIFEST.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in old) + "\n", encoding="utf-8")
        return 0

    todo = []
    for i, p in enumerate(bases()):
        d = DAMAGES[i % len(DAMAGES)]
        stem = p.stem[-24:]
        if not (OUT / f"{stem}__splice.png").exists():
            todo.append((p, stem, d, i))
    todo = todo[: args.limit]
    print(f"待生成 {len(todo)} 张底图（limit={args.limit}）")
    if args.dry_run:
        for p, stem, d, _ in todo:
            print(f"- {p.name} -> {stem}: {d}")
        return 0

    key = os.getenv("IMAGE_API_KEY")
    if not key:
        print("缺少 IMAGE_API_KEY")
        return 1
    from openai import OpenAI

    client = OpenAI(api_key=key, base_url=os.getenv("IMAGE_BASE_URL"), timeout=300)
    model = os.getenv("IMAGE_MODEL", "gpt-image-2")
    OUT.mkdir(parents=True, exist_ok=True)

    ok = 0
    for p, stem, d, i in todo:
        t0 = time.time()
        base = square(p)
        buf = io.BytesIO()
        base.save(buf, "PNG")
        buf.name = "base.png"
        buf.seek(0)
        try:
            r = client.images.edit(model=model, image=buf, prompt=PROMPT.format(d=d), size="1024x1024", n=1)
            edited = Image.open(io.BytesIO(base64.b64decode(r.data[0].b64_json))).convert("RGB")
        except Exception as e:  # noqa: BLE001
            print(f"失败 {stem}: {type(e).__name__}: {e}")
            continue
        edited = edited.resize((SIZE, SIZE), Image.LANCZOS)
        sp, box = splice(base, edited)
        edited.save(OUT / f"{stem}__full.png")
        sp.save(OUT / f"{stem}__splice.png")
        base.save(OUT / f"{stem}__base.png")
        with open(MANIFEST, "a", encoding="utf-8") as f:
            for kind in ("full", "splice"):
                f.write(json.dumps({"file": f"edit/{stem}__{kind}.png", "base": f"edit/{stem}__base.png", "kind": kind,
                                    "box": box if kind == "splice" else None, "damage": d, "truth": "fake_edit",
                                    "generator": model}, ensure_ascii=False) + "\n")
        ok += 1
        print(f"完成 {stem}（{time.time() - t0:.0f}s）")
    print(f"成功 {ok}/{len(todo)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
