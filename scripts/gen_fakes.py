"""用生图模型批量生成"假破损"评测样本（仅用于评测，不属于系统运行时依赖）。

按 产品知识库(products.yaml) × 可能的破损类型 组合出提示词，图片存 data/images/gen/，
标签写入 data/seed/gen_manifest.jsonl（truth=fake, generator=模型名）。

用法:
  python scripts/gen_fakes.py --dry-run               # 只列出将要生成的组合，不花额度
  python scripts/gen_fakes.py --limit 6               # 最多生成 6 张
  python scripts/gen_fakes.py --sku SKU-SERUM-GLASS-30 --damage leak --per 2
已存在的文件自动跳过，可随时中断后续跑。
"""
import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "images" / "gen"
MANIFEST = ROOT / "data" / "seed" / "gen_manifest.jsonl"
load_dotenv(ROOT / ".env")

CONTAINER = {
    ("glass_bottle", "dropper"): "a 30ml clear glass dropper serum bottle with a rubber bulb",
    ("glass_bottle", "pump"): "a 30ml glass foundation bottle with a pump head",
    ("plastic_tube", "flip_cap"): "a 125ml plastic squeeze tube of facial cleanser with a flip cap",
    ("glass_jar", "screw_lid"): "a 50ml glass cream jar with a screw lid",
    ("plastic_bottle", "pump"): "a 50ml plastic lotion bottle with a pump head",
}
DAMAGE = {
    "leak": "liquid has leaked out around the {part} and pooled on the surface, the bottle is wet",
    "container_crack": "a visible crack runs across the {part}",
    "pump_broken": "the pump head is snapped off and tilted at an odd angle",
    "outer_box_damage": "its cardboard outer box is crushed and torn at one corner",
}
PART = {"glass_bottle": "glass neck", "glass_jar": "jar wall", "plastic_bottle": "bottle neck", "plastic_tube": "seam"}
SCENES = ["on a bathroom counter", "on a wooden table by a window", "on a bed with a blanket", "on a kitchen counter"]
STYLE = ("Realistic casual smartphone photo taken by a customer, slightly uneven indoor lighting, "
         "no brand names or readable logos, no text, close-up of the damage.")


def prompt(product: dict, damage: str, i: int) -> str:
    base = CONTAINER[(product["container"], product["closure"])]
    part = PART.get(product["container"], "body")
    return f"{STYLE} {base} {SCENES[i % len(SCENES)]}; {DAMAGE[damage].format(part=part)}."


def combos(args):
    products = yaml.safe_load((ROOT / "data" / "seed" / "products.yaml").read_text(encoding="utf-8"))
    for p in products:
        if args.sku and p["sku_id"] != args.sku:
            continue
        for d in p["possible_damage"]:
            if args.damage and d != args.damage:
                continue
            for i in range(args.per):
                yield p, d, i


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sku")
    ap.add_argument("--damage")
    ap.add_argument("--per", type=int, default=1)
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    todo = [(p, d, i) for p, d, i in combos(args) if not (OUT / f"{p['sku_id']}__{d}__{i}.png").exists()]
    todo = todo[: args.limit]
    print(f"待生成 {len(todo)} 张（limit={args.limit}）")
    if args.dry_run:
        for p, d, i in todo:
            print(f"- {p['sku_id']} / {d} / #{i}: {prompt(p, d, i)}")
        return 0

    key = os.getenv("IMAGE_API_KEY")
    if not key:
        print("缺少 IMAGE_API_KEY，请在 .env 中配置")
        return 1
    from openai import OpenAI

    client = OpenAI(api_key=key, base_url=os.getenv("IMAGE_BASE_URL"), timeout=240)
    model = os.getenv("IMAGE_MODEL", "gpt-image-2")
    OUT.mkdir(parents=True, exist_ok=True)

    ok = 0
    for p, d, i in todo:
        name = f"{p['sku_id']}__{d}__{i}.png"
        pr = prompt(p, d, i)
        t0 = time.time()
        try:
            r = client.images.generate(model=model, prompt=pr, size="1024x1024", n=1)
            (OUT / name).write_bytes(base64.b64decode(r.data[0].b64_json))
        except Exception as e:  # noqa: BLE001
            print(f"失败 {name}: {type(e).__name__}: {e}")
            continue
        with open(MANIFEST, "a", encoding="utf-8") as f:
            f.write(json.dumps({"file": f"gen/{name}", "sku_id": p["sku_id"], "damage": d, "truth": "fake",
                                "generator": model, "prompt": pr}, ensure_ascii=False) + "\n")
        ok += 1
        print(f"完成 {name}（{time.time() - t0:.0f}s）")
    print(f"成功 {ok}/{len(todo)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
