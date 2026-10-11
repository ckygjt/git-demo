"""用开源 inpainting 模型（FLUX.1-Fill-dev / SDXL-inpainting）在 GPU 上批量造局部篡改评测样本（仅用于评测）。

每个样本（一张底图 x 一个生成器 x 一种破损 x 一个掩码）产出：
  full            模型整图输出
  splice          仅把掩码内部的编辑结果羽化贴回底图（掩码外与底图逐像素一致）
  control_splice  同一掩码、同一流程，prompt 为"完好无损"的对照
  mask            GT 掩码（白色为被编辑区域）
manifest 每个样本写两行：splice 与 control_splice（full 图以 full_file 字段指向）。已完成的样本自动跳过，可随时中断续跑。

用法:
  python scripts/gen_edits_local.py --dry-run
  python scripts/gen_edits_local.py --only flux --limit 1 --prefix edit2_smoke --manifest data/seed/edit2_smoke_manifest.jsonl
  python scripts/gen_edits_local.py --verify --manifest data/seed/edit2_manifest.jsonl
  python scripts/gen_edits_local.py --backend fake --limit 3   # 无 GPU 的流程自测
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SIZE = 1024
GENERATORS = ("flux", "sdxl")
SHAPES = ("rect", "ellipse", "blob")
AREA_MIN, AREA_MAX = 0.05, 0.25
DIFF_MIN, DIFF_THR = 0.005, 8
GEN_CFG = {"flux": {"steps": 28, "guidance": 30.0}, "sdxl": {"steps": 30, "guidance": 8.0}}
REPO_ID = {"flux": "black-forest-labs/FLUX.1-Fill-dev", "sdxl": "diffusers/stable-diffusion-xl-1.0-inpainting-0.1"}

ALLOWED = {
    "plastic_bottle": ["crack", "leak", "pump"],
    "jar": ["crack", "leak", "pump"],
    "compact": ["crack", "pump"],
    "tube": ["tube", "leak"],
    "box": ["box", "label"],
    "other": ["leak", "label"],
}
WORDINGS = {
    "crack": ["a visible crack running across the container body", "a chipped and cracked area on the product surface"],
    "leak": ["liquid leaking out of the product and pooling on the surface beneath it", "a wet glossy spill of product spreading around the damaged spot"],
    "pump": ["the cap or pump head broken and tilted at an odd angle", "the lid snapped open and hanging loose"],
    "box": ["the cardboard box crushed and torn at the corner", "a dented, torn and creased box"],
    "tube": ["the tube dented and squeezed with product oozing from the edge", "a deeply creased and flattened tube"],
    "label": ["the label torn and peeling off", "the packaging label scratched and ripped"],
}
PROMPT = "A casual customer photo of a damaged beauty product: {d}. Realistic lighting and texture matching the photo. No text."
CONTROL_PROMPT = "A casual customer photo of an intact, undamaged beauty product, unchanged, realistic lighting and texture. No text."


def square(path: Path) -> Image.Image:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    s = min(w, h)
    im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
    return im.resize((SIZE, SIZE), Image.LANCZOS)


def make_mask(rng: np.random.Generator, shape: str) -> Image.Image:
    for _ in range(100):
        area = rng.uniform(0.06, 0.22) * SIZE * SIZE
        cx, cy = (float(np.clip(rng.normal(0.5, 0.12), 0.25, 0.75)) * SIZE for _ in range(2))
        ar = rng.uniform(0.6, 1.6)
        img = Image.new("L", (SIZE, SIZE), 0)
        d = ImageDraw.Draw(img)
        if shape == "rect":
            w = (area * ar) ** 0.5
            h = area / w
            d.rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], fill=255)
        else:
            parts = [(0.0, 0.0, 1.0)] if shape == "ellipse" else [(rng.normal(0, .12) * SIZE, rng.normal(0, .12) * SIZE, rng.uniform(.35, .6)) for _ in range(4)]
            for dx, dy, k in parts:
                a = (area * k * ar / np.pi) ** 0.5
                b = area * k / (np.pi * a)
                d.ellipse([cx + dx - a, cy + dy - b, cx + dx + a, cy + dy + b], fill=255)
        frac = float((np.asarray(img) > 0).mean())
        if AREA_MIN <= frac <= AREA_MAX:
            return img
    raise RuntimeError("mask generation failed")


def soft_mask(mask: np.ndarray) -> np.ndarray:
    """只向掩码内部羽化，保证掩码外权重严格为 0。"""
    m = Image.fromarray((mask * 255).astype("uint8"))
    inner = np.asarray(m.filter(ImageFilter.MinFilter(17)).filter(ImageFilter.GaussianBlur(4)), dtype=np.float32) / 255
    return np.minimum(inner, mask.astype(np.float32))


def splice(base: Image.Image, edited: Image.Image, mask: np.ndarray) -> Image.Image:
    s = soft_mask(mask)[..., None]
    out = np.asarray(base, dtype=np.float32) * (1 - s) + np.asarray(edited, dtype=np.float32) * s
    return Image.fromarray(np.rint(out).astype("uint8"))


def diff_frac(a: Image.Image, b: Image.Image) -> float:
    d = np.abs(np.asarray(a, dtype=np.int16) - np.asarray(b, dtype=np.int16)).max(axis=2)
    return float((d > DIFF_THR).mean())


def seed_of(key: str) -> int:
    return int(hashlib.sha1(key.encode()).hexdigest()[:8], 16)


def load_bases(screened: Path) -> list[dict]:
    rows = [json.loads(l) for l in screened.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = sorted((r for r in rows if r.get("keep") and r["truth"] == "real_intact"), key=lambda r: r["file"])
    return [{**r, "bid": f"b{i:02d}"} for i, r in enumerate(rows)]


def plan(bases: list[dict], per_base: int) -> list[dict]:
    out = []
    for bi, b in enumerate(bases):
        allowed = ALLOWED.get(b.get("container"), ALLOWED["other"])
        for v in range(per_base):
            dtype = allowed[(bi + v) % len(allowed)]
            out.append({"id": f"{b['bid']}_v{v}", "bid": b["bid"], "src": b["file"], "gen": GENERATORS[(bi + v) % 2], "damage_type": dtype,
                        "damage": WORDINGS[dtype][((bi + v) // len(allowed)) % 2], "shape": SHAPES[v % 3], "seed": seed_of(f"{b['bid']}-{v}")})
    return out


class Fake:
    """无 GPU 的流程自测后端：整图轻微偏色加噪声，模拟 VAE 重编码。"""
    def run(self, base, mask, prompt, seed, cfg):
        rng = np.random.default_rng(seed)
        arr = np.asarray(base, dtype=np.float32) * rng.uniform(0.9, 1.1, 3) + rng.normal(0, 3, (SIZE, SIZE, 3))
        m = np.asarray(mask) > 0
        arr[m] = arr[m] * 0.5 + 60
        return Image.fromarray(np.clip(arr, 0, 255).astype("uint8"))


class Flux:
    def __init__(self, path):
        import torch
        from diffusers import FluxFillPipeline
        self.torch = torch
        self.pipe = FluxFillPipeline.from_pretrained(path, torch_dtype=torch.bfloat16).to("cuda")

    def run(self, base, mask, prompt, seed, cfg):
        g = self.torch.Generator("cpu").manual_seed(seed)
        return self.pipe(prompt=prompt, image=base, mask_image=mask, height=SIZE, width=SIZE, guidance_scale=cfg["guidance"],
                         num_inference_steps=cfg["steps"], max_sequence_length=512, generator=g).images[0].convert("RGB")


class Sdxl:
    def __init__(self, path):
        import torch
        from diffusers import AutoPipelineForInpainting
        self.torch = torch
        self.pipe = AutoPipelineForInpainting.from_pretrained(path, torch_dtype=torch.float16, variant="fp16").to("cuda")

    def run(self, base, mask, prompt, seed, cfg):
        g = self.torch.Generator("cpu").manual_seed(seed)
        return self.pipe(prompt=prompt, image=base, mask_image=mask, height=SIZE, width=SIZE, strength=0.99, guidance_scale=cfg["guidance"],
                         num_inference_steps=cfg["steps"], generator=g).images[0].convert("RGB")


def load_backend(gen: str, args):
    if args.backend == "fake":
        return Fake()
    return (Flux if gen == "flux" else Sdxl)(getattr(args, f"{gen}_path") or REPO_ID[gen])


def bbox_rel(mask: np.ndarray) -> list[float]:
    ys, xs = np.where(mask)
    return [round(xs.min() / SIZE, 4), round(ys.min() / SIZE, 4), round((xs.max() + 1) / SIZE, 4), round((ys.max() + 1) / SIZE, 4)]


def process(s: dict, backend, args, out: Path, prefix: str, bases_dir: Path) -> list[dict] | None:
    rng = np.random.default_rng(s["seed"])
    mask_img = make_mask(rng, s["shape"])
    mask = np.asarray(mask_img) > 0
    base_p = out / f"{s['bid']}__base.png"
    if base_p.exists():
        base = Image.open(base_p).convert("RGB")
    else:
        base = square(bases_dir / s["src"])
        base.save(base_p)
    cfg = GEN_CFG[s["gen"]]
    for attempt in range(3):
        seed = s["seed"] + 7919 * attempt
        full = backend.run(base, mask_img, PROMPT.format(d=s["damage"]), seed, cfg)
        sp = splice(base, full, mask)
        d = diff_frac(base, sp)
        if d >= DIFF_MIN:
            break
    else:
        return None
    ctrl_full = backend.run(base, mask_img, CONTROL_PROMPT, seed + 1, cfg)
    ctrl = splice(base, ctrl_full, mask)
    names = {k: f"{s['id']}__{k}.png" for k in ("full", "splice", "control", "mask")}
    full.save(out / names["full"])
    sp.save(out / names["splice"])
    ctrl.save(out / names["control"])
    mask_img.save(out / names["mask"])
    common = {"base": f"{prefix}/{base_p.name}", "full_file": f"{prefix}/{names['full']}", "mask": f"{prefix}/{names['mask']}", "box": bbox_rel(mask),
              "damage": s["damage"], "damage_type": s["damage_type"], "generator": s["gen"] if args.backend != "fake" else "fake", "seed": seed,
              "steps": cfg["steps"], "guidance": cfg["guidance"], "mask_area": round(float(mask.mean()), 4), "mask_shape": s["shape"], "id": s["id"]}
    return [{**common, "file": f"{prefix}/{names['splice']}", "kind": "splice", "truth": "fake_edit", "diff_frac": round(d, 4)},
            {**common, "file": f"{prefix}/{names['control']}", "kind": "control_splice", "truth": "control", "diff_frac": round(diff_frac(base, ctrl), 4)}]


def verify(manifest: Path, images: Path) -> int:
    rows = [json.loads(l) for l in manifest.read_text(encoding="utf-8").splitlines() if l.strip()]
    bad = []
    for r in rows:
        base = np.asarray(Image.open(images / r["base"]).convert("RGB"))
        m = np.asarray(Image.open(images / r["mask"]).convert("L")) > 0
        im = np.asarray(Image.open(images / r["file"]).convert("RGB"))
        area = float(m.mean())
        if not AREA_MIN <= area <= AREA_MAX:
            bad.append((r["file"], f"mask 面积 {area:.3f}"))
        if not np.array_equal(base[~m], im[~m]):
            bad.append((r["file"], "掩码外与底图不一致"))
        if r["kind"] == "splice" and diff_frac(Image.fromarray(base), Image.fromarray(im)) < DIFF_MIN:
            bad.append((r["file"], "差异 <0.5%"))
        if not (images / r["full_file"]).exists():
            bad.append((r["file"], "缺少 full 图"))
    print(f"verify: {len(rows)} 行, 失败 {len(bad)}")
    for f, why in bad[:20]:
        print("  FAIL", f, why)
    return 1 if bad else 0


def report(manifest: Path, planned: int) -> None:
    rows = [json.loads(l) for l in manifest.read_text(encoding="utf-8").splitlines() if l.strip()]
    sp = [r for r in rows if r["kind"] == "splice"]
    print(f"计划 {planned} 个样本，完成 {len(sp)}，丢弃 {planned - len(sp)}（manifest {len(rows)} 行）")
    for key in ("generator", "damage_type", "mask_shape"):
        cnt: dict[str, int] = {}
        for r in sp:
            cnt[r[key]] = cnt.get(r[key], 0) + 1
        print(f"  按 {key}: {dict(sorted(cnt.items()))}")
    if sp:
        print(f"  splice diff_frac 均值 {np.mean([r['diff_frac'] for r in sp]):.3f}；对照 diff_frac 均值 {np.mean([r['diff_frac'] for r in rows if r['kind'] == 'control_splice']):.3f}")
        print(f"  掩码面积 {min(r['mask_area'] for r in sp):.3f}–{max(r['mask_area'] for r in sp):.3f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images-dir", type=Path, default=ROOT / "data" / "images")
    ap.add_argument("--screened", type=Path, default=ROOT / "data" / "seed" / "real_screened.jsonl")
    ap.add_argument("--manifest", type=Path, default=ROOT / "data" / "seed" / "edit2_manifest.jsonl")
    ap.add_argument("--prefix", default="edit2")
    ap.add_argument("--per-base", type=int, default=5)
    ap.add_argument("--only", choices=GENERATORS)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--backend", choices=("real", "fake"), default="real")
    ap.add_argument("--flux-path")
    ap.add_argument("--sdxl-path")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    if args.verify:
        return verify(args.manifest, args.images_dir)
    if args.report:
        report(args.manifest, len(plan(load_bases(args.screened), args.per_base)))
        return 0
    samples = plan(load_bases(args.screened), args.per_base)
    if args.only:
        samples = [s for s in samples if s["gen"] == args.only]
    if args.limit:
        samples = samples[: args.limit]
    done = {json.loads(l)["id"] for l in args.manifest.read_text(encoding="utf-8").splitlines() if l.strip()} if args.manifest.exists() else set()
    todo = [s for s in samples if s["id"] not in done]
    print(f"计划 {len(samples)} 个样本，已完成 {len(samples) - len(todo)}，待生成 {len(todo)}；各生成器：{ {g: sum(s['gen'] == g for s in todo) for g in GENERATORS} }")
    if args.dry_run:
        areas = [float((np.asarray(make_mask(np.random.default_rng(s['seed']), s['shape'])) > 0).mean()) for s in samples]
        print(f"掩码面积 min={min(areas):.3f} max={max(areas):.3f} mean={np.mean(areas):.3f}")
        for s in todo[:5]:
            print(" ", s["id"], s["gen"], s["damage_type"], s["shape"], s["seed"])
        return 0

    out = args.images_dir / args.prefix
    out.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    rejects = 0
    t0 = time.time()
    for gen in GENERATORS:
        part = [s for s in todo if s["gen"] == gen]
        if not part:
            continue
        backend = load_backend(gen, args)
        for i, s in enumerate(part, 1):
            rows = process(s, backend, args, out, args.prefix, args.images_dir)
            if rows is None:
                rejects += 1
                print(f"[{gen} {i}/{len(part)}] {s['id']} 丢弃（差异过小）", flush=True)
                continue
            with args.manifest.open("a", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            print(f"[{gen} {i}/{len(part)}] {s['id']} {s['damage_type']} diff={rows[0]['diff_frac']:.3f} 累计 {time.time() - t0:.0f}s", flush=True)
        del backend
        if args.backend == "real":
            import torch
            torch.cuda.empty_cache()
    print(f"完成，丢弃 {rejects}，耗时 {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
