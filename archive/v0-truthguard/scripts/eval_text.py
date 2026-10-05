"""文案检测基线评估：在 samples/texts.csv 上跑规则引擎，输出混淆情况。

用途：路演时给出可量化的基线指标（仅规则层，不含 LLM，结果可复现）。
用法：python scripts/eval_text.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.detection import text_detector  # noqa: E402

CSV_PATH = ROOT / "samples" / "texts.csv"
THRESHOLD = 50.0  # text_score >= 50 判为"有风险"


def load_rows() -> list[tuple[str, str]]:
    with CSV_PATH.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [(r["label"].strip(), r["text"].strip()) for r in reader]


def main() -> None:
    rows = load_rows()
    if not rows:
        print("样本为空，请检查 samples/texts.csv")
        return

    stats = {k: {"total": 0, "flagged": 0} for k in ("fake", "real", "gray")}
    for label, text in rows:
        res = text_detector.analyze(text, use_llm=False)
        flagged = res.text_score >= THRESHOLD or res.redline
        stats[label]["total"] += 1
        stats[label]["flagged"] += int(flagged)

    fake = stats["fake"]
    real = stats["real"]
    gray = stats["gray"]

    recall = fake["flagged"] / fake["total"] if fake["total"] else 0.0
    fpr = real["flagged"] / real["total"] if real["total"] else 0.0
    flagged_total = fake["flagged"] + real["flagged"] + gray["flagged"]
    precision = fake["flagged"] / flagged_total if flagged_total else 0.0

    print("=" * 52)
    print(f"样本总数：{len(rows)}（fake {fake['total']} / real {real['total']} / gray {gray['total']}）")
    print(f"违规文案召回率 Recall：{recall:.1%}  （{fake['flagged']}/{fake['total']}）")
    print(f"合规文案误报率 FPR  ：{fpr:.1%}  （{real['flagged']}/{real['total']}）")
    print(f"告警精确率 Precision：{precision:.1%}")
    print(f"灰色地带告警数      ：{gray['flagged']}/{gray['total']}（体现分级而非一刀切）")
    print("=" * 52)


if __name__ == "__main__":
    main()
