"""生成合成测试样本图：真实（real）/ 篡改（fake）/ 灰色地带（gray）。

说明：合成样本用于验证取证链路与演示，不能替代真实拍摄素材；
正式路演请补充真实商品图与真实篡改图（见 samples/README.md）。
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "samples"


def _base(rng: np.random.Generator, size: int = 800) -> np.ndarray:
    yy, xx = np.mgrid[0:size, 0:size]
    img = np.zeros((size, size, 3), dtype=np.float32)
    img[..., 0] = 205 + 28 * np.sin(xx / 55.0)
    img[..., 1] = 178 + 26 * np.sin(yy / 55.0)
    img[..., 2] = 196 + 18 * np.cos((xx + yy) / 90.0)
    return np.clip(img + rng.normal(0, 3.0, img.shape), 0, 255)


def _save(arr: np.ndarray, path: Path, quality: int = 92) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr.astype(np.uint8)).save(path, "JPEG", quality=quality)


def make_real(idx: int, rng: np.random.Generator) -> None:
    """真实样本：全局噪声一致，无二次编辑。"""
    _save(_base(rng), OUT / "real" / f"real_{idx:02d}.jpg")


def make_fake(idx: int, rng: np.random.Generator) -> None:
    """篡改样本：粘贴噪声特征不同的外来区域，模拟拼接换肤。"""
    img = _base(rng)
    h, w, _ = img.shape
    ph, pw = h // 3, w // 3
    y0, x0 = h // 4, w // 2
    patch = rng.normal(0, 42, (ph, pw, 3)) + np.array([152, 118, 126])
    img[y0 : y0 + ph, x0 : x0 + pw] = np.clip(patch, 0, 255)
    _save(img, OUT / "fake" / f"fake_{idx:02d}.jpg")


def make_gray(idx: int, rng: np.random.Generator) -> None:
    """灰色地带：仅做轻度磨皮，无外来区域，考验 Agent 是否一刀切。"""
    img = Image.fromarray(_base(rng).astype(np.uint8))
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    arr = np.asarray(img, dtype=np.float32)
    arr = np.clip(arr + rng.normal(0, 2.0, arr.shape), 0, 255)
    _save(arr, OUT / "gray" / f"gray_{idx:02d}.jpg")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", type=int, default=4)
    parser.add_argument("--fake", type=int, default=6)
    parser.add_argument("--gray", type=int, default=3)
    args = parser.parse_args()

    rng = np.random.default_rng(2026)
    for i in range(1, args.real + 1):
        make_real(i, rng)
    for i in range(1, args.fake + 1):
        make_fake(i, rng)
    for i in range(1, args.gray + 1):
        make_gray(i, rng)
    print(f"样本已生成于 {OUT}：real×{args.real} fake×{args.fake} gray×{args.gray}")


if __name__ == "__main__":
    main()
