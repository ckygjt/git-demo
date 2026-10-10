"""局部篡改评测：TruFor 与 Community Forensics 在 真图 vs 局部编辑图 上的区分度。

集合：real_damaged / real_intact（原生真图）、edit_base（同一批底图的 1024 方形重采样版，与编辑图同处理，作配对阴性）、
      edit_full（编辑 API 整图输出）、edit_splice（仅编辑区域贴回原图）。
口径：raw 原图；norm 最长边 768 + JPEG q85（模拟平台压缩）。
关键对比是 edit_base（阴性）vs edit_full/edit_splice（阳性），排除"重采样/PNG"造成的混淆。
输出 data/eval/forensics_tamper.json。

用法: python scripts/eval_tamper.py
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
from app.tools import forensics_aigc, forensics_tamper  # noqa: E402
from eval_images import load_sets  # noqa: E402
from eval_forensics import auc, to_norm  # noqa: E402


def load_all() -> dict[str, list[Path]]:
    sets = {k: v for k, v in load_sets(0).items() if k != "fake_damaged"}
    img = ROOT / "data" / "images"
    man = [json.loads(l) for l in (ROOT / "data" / "seed" / "edit_manifest.jsonl").read_text(encoding="utf-8").splitlines() if l]
    sets["edit_base"] = sorted({img / r["base"] for r in man})
    sets["edit_full"] = [img / r["file"] for r in man if r["kind"] == "full"]
    sets["edit_splice"] = [img / r["file"] for r in man if r["kind"] == "splice"]
    return {k: [p for p in v if p.exists()] for k, v in sets.items()}


def main() -> int:
    sys.stdout.reconfigure(errors="replace")
    use_t, use_a = forensics_tamper.available(), forensics_aigc.available()
    print("TruFor:", use_t, " CommFor:", use_a)
    sets = load_all()
    print({k: len(v) for k, v in sets.items()})
    rows = []
    t0 = time.time()
    for k, ps in sets.items():
        for p in ps:
            row = {"set": k, "file": p.name}
            for mode, loader in (("raw", lambda q: Image.open(q).convert("RGB")), ("norm", to_norm)):
                im = loader(p)
                if use_t:
                    r = forensics_tamper.predict(im)
                    row[f"tf_{mode}"] = r["score"]
                    row[f"tf_map_{mode}"] = r["map_mean"]
                if use_a:
                    row[f"cf_{mode}"] = forensics_aigc.predict(im)
            rows.append(row)
    print(f"推理 {len(rows)} 张，{time.time() - t0:.0f}s")
    out = ROOT / "data" / "eval"
    out.mkdir(parents=True, exist_ok=True)
    (out / "forensics_tamper.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")

    def g(k, key):
        return [r[key] for r in rows if r["set"] == k and key in r]

    keys = [(f"{m}_{mode}", f"{name}/{mode}") for m, name in (("tf", "TruFor.score"), ("tf_map", "TruFor.map_mean"), ("cf", "CommFor"))
            for mode in ("raw", "norm")]
    for key, label in keys:
        if not g("edit_base", key):
            continue
        print(f"\n== {label} ==")
        for k in sets:
            v = g(k, key)
            if v:
                print(f"  {k:13s} n={len(v):2d} 均值={sum(v)/len(v):.3f} 中位={sorted(v)[len(v)//2]:.3f} 最大={max(v):.3f}")
        native = g("real_damaged", key) + g("real_intact", key)
        print(f"  AUC 配对(base vs full)   = {auc(g('edit_base', key), g('edit_full', key)):.3f}")
        print(f"  AUC 配对(base vs splice) = {auc(g('edit_base', key), g('edit_splice', key)):.3f}")
        print(f"  AUC 原生真图 vs splice   = {auc(native, g('edit_splice', key)):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
