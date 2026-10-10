"""S1b：局部篡改检测与定位（TruFor, CVPR 2023；仅限非商业/研究用途，见 third_party/trufor 许可）。

输出整图分数 score（越高越可能被篡改）、异常定位图 map 与可靠性图 conf。
权重路径环境变量 TRUFOR_WEIGHTS，默认 datasets/trufor/weights/trufor.pth.tar。
依赖缺失（torch/timm/yacs）或权重不存在时 available() 为 False，调用方应降级。
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "third_party" / "trufor" / "test_docker" / "src"
DEFAULT_WEIGHTS = ROOT / "datasets" / "trufor" / "weights" / "trufor.pth.tar"
MAX_SIDE = 1536

_state: dict = {}


def weights_path() -> Path:
    return Path(os.getenv("TRUFOR_WEIGHTS", str(DEFAULT_WEIGHTS)))


def available() -> bool:
    if not weights_path().exists() or not SRC.exists():
        return False
    try:
        import timm  # noqa: F401
        import torch  # noqa: F401
        import yacs  # noqa: F401
    except ImportError:
        return False
    return True


def _load():
    if "model" in _state:
        return _state["model"], _state["dev"]
    import torch
    from yacs.config import CfgNode as CN

    sys.path.insert(0, str(SRC))
    try:
        from config import _C as base_cfg
        from models.cmx.builder_np_conf import myEncoderDecoder
    finally:
        sys.path.remove(str(SRC))

    cfg = base_cfg.clone()
    cfg.defrost()
    cfg.merge_from_file(str(SRC / "trufor.yaml"))
    cfg.freeze()
    del CN

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = myEncoderDecoder(cfg=cfg)
    ckpt = torch.load(str(weights_path()), map_location="cpu", weights_only=False)
    model.load_state_dict(ckpt["state_dict"])
    model.eval().to(dev)
    _state.update(model=model, dev=dev)
    return model, dev


def predict(image: bytes | Image.Image | Path) -> dict:
    """返回 {score, map(H×W float), conf(H×W float), bbox(相对坐标或None), map_mean}。"""
    import torch
    import torch.nn.functional as F

    model, dev = _load()
    if isinstance(image, (bytes, bytearray)):
        im = Image.open(io.BytesIO(image))
    elif isinstance(image, Path):
        im = Image.open(image)
    else:
        im = image
    im = im.convert("RGB")
    if max(im.size) > MAX_SIDE:
        im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    arr = np.array(im)
    x = torch.tensor(arr.transpose(2, 0, 1), dtype=torch.float).unsqueeze(0) / 256.0
    with torch.no_grad():
        pred, conf, det, _ = model(x.to(dev))
        amap = F.softmax(torch.squeeze(pred, 0), dim=0)[1].cpu().numpy()
        cmap = torch.sigmoid(torch.squeeze(conf, 0))[0].cpu().numpy() if conf is not None else None
        score = float(torch.sigmoid(det).item()) if det is not None else float(amap.mean())
    ys, xs = np.where(amap > 0.5)
    h, w = amap.shape
    bbox = None
    if len(xs) > 0.002 * h * w:
        bbox = [float(xs.min() / w), float(ys.min() / h), float(xs.max() / w), float(ys.max() / h)]
    return {"score": score, "map": amap, "conf": cmap, "bbox": bbox, "map_mean": float(amap.mean())}
