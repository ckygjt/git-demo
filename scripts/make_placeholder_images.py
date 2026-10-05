"""生成 P0 占位凭证图（P1 用真实拍摄/生成样本替换）。

- 每张图用不同随机色块构图，保证彼此 pHash 距离足够大
- T1003 = H0001 缩放 + 重压缩（模拟同图多单）
- T1007 = 重度模糊（模拟质量不合格）
- T1002 写入早于签收时间的 EXIF 拍摄时间（模拟时间线矛盾）
"""
import io
import json
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "images"
SEED = ROOT / "data" / "seed"

SIZE = 800


def compose(seed: int, label: str) -> Image.Image:
    rnd = random.Random(seed)
    img = Image.new("RGB", (SIZE, SIZE), tuple(rnd.randint(150, 240) for _ in range(3)))
    d = ImageDraw.Draw(img)
    for _ in range(14):
        x1, y1 = rnd.randint(0, SIZE - 100), rnd.randint(0, SIZE - 100)
        x2, y2 = x1 + rnd.randint(60, 400), y1 + rnd.randint(60, 400)
        d.rectangle([x1, y1, x2, y2], fill=tuple(rnd.randint(0, 255) for _ in range(3)))
    bx = rnd.randint(250, 400)
    d.rounded_rectangle([bx, 220, bx + 160, 680], radius=30, fill=(250, 250, 250), outline=(40, 40, 40), width=4)
    d.rectangle([bx + 55, 150, bx + 105, 220], fill=(60, 60, 60))
    d.text((20, 20), f"PLACEHOLDER {label}", fill=(0, 0, 0))
    return img


def save(img: Image.Image, name: str, exif_time: str | None = None) -> None:
    kwargs = {"quality": 92}
    if exif_time:
        exif = Image.Exif()
        exif[0x0110] = "PlaceholderCam"
        exif[0x8769] = {0x9003: exif_time}
        kwargs["exif"] = exif.tobytes()
    img.save(OUT / name, "JPEG", **kwargs)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tickets = json.loads((SEED / "tickets.json").read_text(encoding="utf-8"))
    names = [n for t in tickets for n in t["images"]]

    for i, name in enumerate(sorted(set(names))):
        if name in ("T1003_1.jpg", "T1007_1.jpg"):
            continue
        img = compose(1000 + i * 7, name)
        save(img, name, "2026:09:24 20:15:00" if name == "T1002_1.jpg" else None)

    base = Image.open(OUT / "H0001_1.jpg")
    buf = io.BytesIO()
    base.resize((720, 720)).save(buf, "JPEG", quality=75)
    Image.open(buf).save(OUT / "T1003_1.jpg", "JPEG", quality=85)

    compose(4242, "T1007_1.jpg").filter(ImageFilter.GaussianBlur(14)).save(OUT / "T1007_1.jpg", "JPEG", quality=85)

    print(f"generated {len(set(names))} images -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
