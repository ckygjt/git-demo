"""端到端演示脚本：不启动前端也能跑通「检测 → Agent 决策」完整闭环。

用法：
    python scripts/demo_flow.py --text "七天美白，医美级效果，100%有效"
    python scripts/demo_flow.py --image samples/fake/01.jpg --text "..."
    python scripts/demo_flow.py --make-demo-image   # 自动生成带拼接痕迹的示例图
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app import config  # noqa: E402
from app.agent.risk_agent import decide  # noqa: E402
from app.detection import image_forensics, llm_vision, text_detector  # noqa: E402

LEVEL_CN = {"low": "低风险", "medium": "中风险", "high": "高风险"}
ACTION_CN = {
    "pass": "通过上架",
    "review": "转人工复核",
    "flag": "警示标记并限流",
    "takedown": "建议下架并触发合规工单",
}


def make_demo_image(path: Path) -> Path:
    """生成一张含拼接区域的示例图（背景平滑 + 外来高频纹理块），用于验证取证链路。"""
    rng = np.random.default_rng(42)
    h, w = 600, 600
    base = np.zeros((h, w, 3), dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    base[..., 0] = 200 + 30 * np.sin(xx / 40.0)
    base[..., 1] = 170 + 30 * np.sin(yy / 40.0)
    base[..., 2] = 190 + 20 * np.cos((xx + yy) / 60.0)
    img = base + rng.normal(0, 1.5, (h, w, 3))

    # 外来区域：噪声水平明显不同 + 边缘锐利，模拟拼接
    patch = rng.normal(0, 45, (180, 220, 3)) + np.array([150, 120, 130])
    img[180:360, 300:520] = np.clip(patch, 0, 255)

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img.astype(np.uint8)).save(path, "JPEG", quality=95)
    return path


def print_report(report) -> None:
    line = "─" * 62
    print(line)
    print(f"风险等级：{LEVEL_CN[report.risk_level]}   风险分：{report.risk_score:.1f}/100")
    print(f"处置动作：{ACTION_CN[report.action]}")
    if report.degraded:
        print("※ 当前为降级模式（未配置 LLM），仅使用本地取证与规则证据")
    print(line)

    if report.image:
        img = report.image
        print(f"[图像] {img.width}×{img.height} {img.format}  可疑度 {img.image_score:.1f}")
        print(f"       热力图已生成：{'是' if img.heatmap else '否'}（{len(img.heatmap or '')} 字符 base64）")
        for e in img.evidence:
            print(f"       · {e.name} | {e.score:.2f} | {e.description}")
    if report.text:
        txt = report.text
        print(f"[文案] 可疑度 {txt.text_score:.1f}  红线命中：{'是' if txt.redline else '否'}")
        for e in txt.evidence:
            print(f"       · {e.name} | {e.score:.2f} | {e.description}")

    print(line)
    print("Agent 推理：")
    print(f"  {report.reasoning}")
    print("处置建议：")
    for s in report.suggestions:
        print(f"  - {s}")
    print(f"{line}\n耗时 {report.elapsed_ms} ms")


def main() -> None:
    parser = argparse.ArgumentParser(description="TruthGuard 端到端演示")
    parser.add_argument("--image", type=str, default="", help="待检测图片路径")
    parser.add_argument("--text", type=str, default="", help="待检测文案")
    parser.add_argument("--make-demo-image", action="store_true", help="生成示例篡改图")
    args = parser.parse_args()

    image = None
    img_path = Path(args.image) if args.image else Path("samples/_demo_fake.jpg")
    if args.make_demo_image or (not args.image and not img_path.exists()):
        img_path = make_demo_image(img_path)
        print(f"已生成示例图：{img_path}")

    if img_path.exists():
        data = img_path.read_bytes()
        image = image_forensics.analyze(data)
        vision = llm_vision.analyze(data, "image/jpeg")
        if vision is not None:
            image.evidence.append(vision)

    text = text_detector.analyze(args.text) if args.text.strip() else None
    if image is None and text is None:
        print("请至少提供 --image 或 --text")
        return

    print(f"LLM 状态：provider={config.LLM_PROVIDER or 'none'} "
          f"enabled={config.ENABLE_LLM} vision={config.VISION_ENABLED}")
    print_report(decide(image, text))


if __name__ == "__main__":
    main()
