"""像素取证评测：Community Forensics 在 真实破损/真实完好/AI假破损 上的区分度。

两种输入口径，用于排查格式泄漏（真图多为 JPEG、假图多为 PNG）：
  raw   原图直接送入
  norm  最长边缩到 768 并重编码 JPEG q85（与 VLM 评测一致）
输出 AUC（real vs fake）和若干阈值下的误报率/检出率，结果写 data/eval/forensics_aigc.json。

用法: python scripts/eval_forensics.py
"""
import io
import json
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
from app.tools import forensics_aigc  # noqa: E402
from eval_images import load_sets  # noqa: E402


def to_norm(path: Path) -> Image.Image:
    im = Image.open(path).convert("RGB")
    im.thumbnail((768, 768))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=85)
    return Image.open(io.BytesIO(b.getvalue()))


def auc(neg: list[float], pos: list[float]) -> float:
    if not neg or not pos:
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def main() -> int:
    sys.stdout.reconfigure(errors="replace")
    if not forensics_aigc.available():
        print("Community Forensics 不可用：缺依赖或权重", forensics_aigc.weights_path())
        return 1
    sets = load_sets(0)
    print({k: len(v) for k, v in sets.items()})
    rows = []
    t0 = time.time()
    for k, ps in sets.items():
        for p in ps:
            try:
                rows.append({"set": k, "file": p.name, "ext": p.suffix.lower(),
                             "raw": forensics_aigc.predict(p),
                             "norm": forensics_aigc.predict(to_norm(p))})
            except Exception as e:  # noqa: BLE001
                print("失败", p.name, type(e).__name__, e)
    print(f"推理 {len(rows)} 张，用时 {time.time() - t0:.1f}s，设备 {forensics_aigc._state.get('dev')}")

    out = ROOT / "data" / "eval"
    out.mkdir(parents=True, exist_ok=True)
    (out / "forensics_aigc.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")

    for mode in ("raw", "norm"):
        g = {k: [r[mode] for r in rows if r["set"] == k] for k in sets}
        real = g["real_damaged"] + g["real_intact"]
        fake = g["fake_damaged"]
        print(f"\n== 口径 {mode} ==")
        for k, v in g.items():
            if v:
                print(f"  {k:13s} n={len(v):2d} 均值={sum(v)/len(v):.3f} 最小={min(v):.3f} 最大={max(v):.3f}")
        print(f"  AUC(真实 vs AI假图) = {auc(real, fake):.3f}   AUC(真实破损 vs AI假图) = {auc(g['real_damaged'], fake):.3f}")
        for th in (0.3, 0.5, 0.7, 0.9):
            fp = sum(x >= th for x in real) / len(real) if real else float("nan")
            tp = sum(x >= th for x in fake) / len(fake) if fake else float("nan")
            print(f"  阈值 {th}: 真图误报 {fp:.0%}  假图检出 {tp:.0%}")
    exts = {}
    for r in rows:
        exts.setdefault((r["set"], r["ext"]), 0)
        exts[(r["set"], r["ext"])] += 1
    print("\n文件格式分布:", exts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
