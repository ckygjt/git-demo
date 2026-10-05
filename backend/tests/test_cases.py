"""端到端用例：10 个演示工单的期望结论（Mock 模式，无需 API Key）。"""
import json
import subprocess
import sys

import pytest

from app import orchestrator
from app.config import IMAGES, ROOT, SEED
from app.fusion import disposition, rules
from app.schemas import Evidence, Polarity, Source, Strength, Verdict


@pytest.fixture(scope="session", autouse=True)
def images():
    if not (IMAGES / "T1001_1.jpg").exists():
        subprocess.run([sys.executable, str(ROOT / "scripts" / "make_placeholder_images.py")], check=True)


def run(tid):
    res = None
    for kind, p in orchestrator.verify(tid):
        if kind == "result":
            res = p
    return res


TICKETS = [t for t in json.loads((SEED / "tickets.json").read_text(encoding="utf-8")) if t.get("status") == "pending"]


@pytest.mark.parametrize("t", TICKETS, ids=[t["ticket_id"] for t in TICKETS])
def test_expected_verdict(t):
    res = run(t["ticket_id"])
    assert res.verdict.value == t["label"]["expected_verdict"], (res.fired_rule, res.reason)


def test_no_forbidden_words_in_scripts():
    for t in TICKETS:
        res = run(t["ticket_id"])
        assert not any(w in res.script for w in disposition.FORBIDDEN)


def test_every_non_credible_has_evidence():
    for t in TICKETS:
        res = run(t["ticket_id"])
        if res.verdict.value in ("doubtful_suspicious", "high_risk", "doubtful_insufficient") and res.fired_rule != "R1b":
            assert res.evidence


def _e(rule, pol, st, rel=True, res=False, conf=0.8):
    return Evidence(source=Source.S1, rule=rule, polarity=pol, strength=st, claim_relevant=rel, resolvable=res, confidence=conf, summary=rule)


def test_weak_signals_never_escalate():
    ev = [_e("a", Polarity.down, Strength.weak), _e("b", Polarity.down, Strength.weak)]
    assert rules.decide(ev)[0] == Verdict.credible


def test_irrelevant_edit_not_counted():
    ev = [_e("beauty", Polarity.down, Strength.strong, rel=False)]
    assert rules.decide(ev)[0] == Verdict.credible


def test_resolvable_conflicts_never_high_risk():
    ev = [_e("a", Polarity.down, Strength.strong, res=True), _e("b", Polarity.down, Strength.strong, res=True)]
    assert rules.decide(ev)[0] == Verdict.doubtful_insufficient


def test_strong_up_offsets_doubtful_but_not_high_risk():
    up = _e("up", Polarity.up, Strength.strong)
    assert rules.decide([_e("a", Polarity.down, Strength.strong), up])[0] == Verdict.credible
    hi = [_e("a", Polarity.down, Strength.strong), _e("b", Polarity.down, Strength.medium), up]
    assert rules.decide(hi)[0] == Verdict.high_risk
