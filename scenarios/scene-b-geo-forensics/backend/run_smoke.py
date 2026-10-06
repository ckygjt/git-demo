"""命令行冒烟：无浏览器跑通三个示例案例（默认 mock 模式，配置 Key 后走真实 API）。

用法：
    cd scenarios/scene-b-geo-forensics/backend
    python run_smoke.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import orchestrator  # noqa: E402
from app.config import ensure_dirs, mock_sources, settings  # noqa: E402
from app.schemas import Artifact, CaseInput  # noqa: E402


def main() -> int:
    ensure_dirs()
    print(f"运行模式：{settings().effective}（agent_mode={settings().mode}）\n")
    cases = mock_sources().get("sample_cases") or []
    if not cases:
        print("未找到示例案例")
        return 1

    for c in cases:
        print("=" * 76)
        print(c.get("title", c.get("id")))
        inp = CaseInput(
            text=(c.get("text") or "").strip(),
            brand=c.get("brand", ""),
            product=c.get("product", ""),
            source_url=c.get("source_url", ""),
            images=[Artifact(name=n, path="", usable=True, note="示例素材")
                    for n in (c.get("images") or [])],
        )
        result = None
        for kind, payload in orchestrator.verify(inp, f"smoke_{c.get('id')}"):
            if kind == "event":
                print(f"  · {payload.step:<12} {payload.status:<7} {payload.detail[:88]}")
            else:
                result = payload
        if not result:
            print("  未产出结果")
            continue
        v = result.verdict
        print(f"  → 结论：{v.level_cn}（风险分 {v.risk_score}，置信度 {v.confidence}）")
        print(f"     依据：{v.reason}")
        print(f"     处置：{result.action_cn}")
        for e in result.evidences:
            print(f"     - [{e.tool_cn}] {e.query} → {e.status_cn}/{e.polarity_cn}{e.weight:+.0f} {e.summary}")
        for m in result.missing_materials:
            print(f"     ? 待补：{m}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
