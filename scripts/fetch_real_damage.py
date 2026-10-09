"""从 Amazon Reviews 2023（McAuley Lab，研究用途）流式筛选真实买家破损晒图，作为"真实破损"候选。

只读到凑够数量就停止，不需要下载整个数据集。图片存 data/images/real_candidates/，
候选清单（评论文本、来源 URL）存 data/seed/real_candidates.jsonl，供人工/模型复核后再采用。
注意：评论文字只说明买家"声称"破损，图里是否真有破损需要复核。

用法: python scripts/fetch_real_damage.py --category All_Beauty --limit 40
"""
import argparse
import json
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
BASES = ["https://hf-mirror.com", "https://huggingface.co"]
PATH = "/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/review_categories/{cat}.jsonl"

DAMAGE = re.compile(r"\b(leak(ed|ing|s)?|spill(ed)?|broke(n)?|crack(ed)?|shatter(ed)?|crush(ed)?|dent(ed)?|pump (broke|snapped|is broken)|came (open|apart)|damaged)\b", re.I)
PACKAGE = re.compile(r"\b(bottle|pump|jar|tube|cap|lid|box|serum|lotion|cream|dropper)\b", re.I)


def open_stream(cat: str):
    for b in BASES:
        try:
            r = requests.get(b + PATH.format(cat=cat), stream=True, timeout=30)
            if r.status_code == 200:
                return r
        except requests.RequestException:
            continue
    raise SystemExit("无法连接数据集源")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", default="All_Beauty")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--mode", choices=["damaged", "intact"], default="damaged")
    ap.add_argument("--max-rating", type=float, default=3.0)
    ap.add_argument("--scan", type=int, default=2_000_000, help="最多扫描的评论行数")
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")
    intact = args.mode == "intact"
    sub = "real_intact" if intact else "real_candidates"
    OUT = ROOT / "data" / "images" / sub
    MANIFEST = ROOT / "data" / "seed" / f"{sub}.jsonl"

    OUT.mkdir(parents=True, exist_ok=True)
    seen = set()
    if MANIFEST.exists():
        seen = {json.loads(l)["review_key"] for l in MANIFEST.read_text(encoding="utf-8").splitlines() if l}
    got = scanned = 0
    for line in open_stream(args.category).iter_lines():
        scanned += 1
        if scanned > args.scan or got >= args.limit:
            break
        try:
            rv = json.loads(line)
        except ValueError:
            continue
        text = f"{rv.get('title', '')} {rv.get('text', '')}"
        if not rv.get("images"):
            continue
        if intact:
            if rv["rating"] < 4 or DAMAGE.search(text) or not PACKAGE.search(text):
                continue
        elif rv["rating"] > args.max_rating or not (DAMAGE.search(text) and PACKAGE.search(text)):
            continue
        key = f"{rv['asin']}_{rv['user_id']}_{rv['timestamp']}"
        if key in seen:
            continue
        saved = 0
        for i, im in enumerate(rv["images"][:2]):
            url = im.get("large_image_url") or im.get("medium_image_url")
            if not url:
                continue
            url = url.replace("images-na.ssl-images-amazon.com", "m.media-amazon.com")
            try:
                resp = requests.get(url, timeout=20)
                resp.raise_for_status()
            except requests.RequestException:
                continue
            name = f"{args.category}_{key}_{i}.jpg".replace("/", "_")
            (OUT / name).write_bytes(resp.content)
            with open(MANIFEST, "a", encoding="utf-8") as f:
                f.write(json.dumps({"file": f"{sub}/{name}", "review_key": key, "rating": rv["rating"],
                                    "text": text[:400], "url": url, "category": args.category,
                                    "truth": "real_intact" if intact else "real_claimed_damage"},
                                   ensure_ascii=False) + "\n")
            saved += 1
        if not saved:
            continue
        seen.add(key)
        got += 1
        print(f"[{got}/{args.limit}] 扫描 {scanned} 行 · ★{rv['rating']} {text[:70]}")
    print(f"完成：扫描 {scanned} 行，收集 {got} 条评论")
    return 0


if __name__ == "__main__":
    sys.exit(main())
