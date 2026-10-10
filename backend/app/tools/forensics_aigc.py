"""S1a：AIGC 整图检测（Community Forensics, CVPR 2025, MIT）。

ViT-S/16@384，单输出 sigmoid，p_fake 越大越可能是 AI 生成。
预处理与官方 eval 一致：短边缩放到 440 → 中心裁剪 384 → ImageNet 归一化。
权重路径由环境变量 COMMFOR_WEIGHTS 指定，默认 datasets/_cf_model384/model.safetensors。
可选依赖（torch/timm/safetensors）缺失或权重不存在时 available() 为 False，调用方应降级。
"""
from __future__ import annotations

import io
import os
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_WEIGHTS = ROOT / "datasets" / "_cf_model384" / "model.safetensors"

_state: dict = {}


def weights_path() -> Path:
    return Path(os.getenv("COMMFOR_WEIGHTS", str(DEFAULT_WEIGHTS)))


def available() -> bool:
    if not weights_path().exists():
        return False
    try:
        import timm  # noqa: F401
        import torch  # noqa: F401
        from safetensors.torch import load_file  # noqa: F401
    except ImportError:
        return False
    return True


def _load():
    if "model" in _state:
        return _state["model"], _state["tf"], _state["dev"]
    import timm
    import torch
    import torchvision.transforms as T
    from safetensors.torch import load_file

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = timm.create_model("vit_small_patch16_384", pretrained=False, num_classes=1)
    sd = load_file(str(weights_path()))
    sd = {(k[4:] if k.startswith("vit.") else k): v for k, v in sd.items()}
    missing, unexpected = model.load_state_dict(sd, strict=False)
    if missing or unexpected:
        raise RuntimeError(f"权重与结构不匹配 missing={missing[:3]} unexpected={unexpected[:3]}")
    model.eval().to(dev)
    tf = T.Compose([
        T.Resize(440),
        T.CenterCrop(384),
        T.ToTensor(),
        T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    _state.update(model=model, tf=tf, dev=dev)
    return model, tf, dev


def predict(image: bytes | Image.Image | Path) -> float:
    """返回 p_fake ∈ [0,1]。"""
    import torch

    model, tf, dev = _load()
    if isinstance(image, (bytes, bytearray)):
        im = Image.open(io.BytesIO(image))
    elif isinstance(image, Path):
        im = Image.open(image)
    else:
        im = image
    x = tf(im.convert("RGB")).unsqueeze(0).to(dev)
    with torch.no_grad():
        return float(torch.sigmoid(model(x)).item())
