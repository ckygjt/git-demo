"""汇总 data/eval 下的离线评测结果，供 /api/eval 展示。只读已落盘的结果，不重新推理。"""
import json
from functools import lru_cache

from .config import ROOT

EVAL_DIR = ROOT / "data" / "eval"

LIMITATIONS = [
    "样本量小：AI 假图 12 张、局部编辑 14 张，且各只有单一生成/编辑模型，数字仅作基线，不代表线上表现。",
    "像素取证在压缩后基本失效：仅 JPEG q95 就让 TruFor 的 AUC 从 0.98 降到 0.52；Community Forensics 在压缩后检不出 AI 假图。",
    "真图 JPEG、假图 PNG 存在格式差异，'原图'口径的高 AUC 可能含格式泄漏，应以压缩/配对口径为准。",
    "因此像素取证只作'高置信才加权'的弱证据，低分不代表真；假图识别主要依赖订单、物流、跨工单、话术一致性与补证流程。",
    "TruFor 许可仅限非商业/研究用途。",
]


def _load(name: str):
    p = EVAL_DIR / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _auc(neg: list[float], pos: list[float]) -> float | None:
    if not neg or not pos:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return round(wins / (len(pos) * len(neg)), 3)


def _mean(v: list[float]) -> float | None:
    return round(sum(v) / len(v), 4) if v else None


def _vlm(rows: list[dict]) -> list[dict]:
    out = []
    for s in sorted({r["set"] for r in rows}):
        rs = [r for r in rows if r["set"] == s]
        ok = [r for r in rs if r.get("vision_ok")]
        probs = [r["ai_prob"] for r in ok if r.get("ai_prob") is not None]
        out.append({"set": s, "n": len(rs), "vision_ok": len(ok), "reported_damage": sum(r["n_damages"] > 0 for r in ok),
                    "ai_flagged": sum(p >= 0.5 for p in probs), "ai_prob_mean": _mean(probs)})
    return out


def _aigc(rows: list[dict]) -> dict:
    real = [r for r in rows if r["set"].startswith("real")]
    fake = [r for r in rows if r["set"] == "fake_damaged"]
    res = {"n_real": len(real), "n_fake": len(fake), "modes": {}}
    for m in ("raw", "norm"):
        rv, fv = [r[m] for r in real], [r[m] for r in fake]
        res["modes"][m] = {"auc": _auc(rv, fv), "real_max": round(max(rv), 4) if rv else None, "fake_mean": _mean(fv),
                           "fake_detected@0.5": sum(x >= 0.5 for x in fv), "real_false_pos@0.5": sum(x >= 0.5 for x in rv)}
    return res


def _tamper(rows: list[dict], ablation: list[dict] | None) -> dict:
    sets = {}
    for r in rows:
        sets.setdefault(r["set"], []).append(r)
    real = sets.get("real_damaged", []) + sets.get("real_intact", [])
    res = {"n": {k: len(v) for k, v in sets.items()}, "real_false_pos": {}, "ablation": ablation or []}
    for m in ("raw", "norm"):
        key = f"tf_{m}"
        rv = [r[key] for r in real if key in r]
        res["real_false_pos"][m] = {f">={t}": sum(x >= t for x in rv) for t in (0.55, 0.8, 0.9)} | {"n": len(rv)}
        res.setdefault("auc", {})[m] = {
            "base_vs_splice": _auc([r[key] for r in sets.get("edit_base", []) if key in r], [r[key] for r in sets.get("edit_splice", []) if key in r]),
            "base_vs_full": _auc([r[key] for r in sets.get("edit_base", []) if key in r], [r[key] for r in sets.get("edit_full", []) if key in r]),
        }
    return res


@lru_cache
def summary() -> dict:
    img, aigc, tamper = _load("image_eval.json"), _load("forensics_aigc.json"), _load("forensics_tamper.json")
    return {
        "available": any(x is not None for x in (img, aigc, tamper)),
        "vlm": _vlm(img) if img else None,
        "aigc": _aigc(aigc) if aigc else None,
        "tamper": _tamper(tamper, _load("tamper_ablation.json")) if tamper else None,
        "limitations": LIMITATIONS,
    }
