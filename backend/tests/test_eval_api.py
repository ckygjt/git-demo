import pytest

pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from app import orchestrator  # noqa: E402
from app.main import app  # noqa: E402
from app.tools import forensics_aigc, forensics_tamper, perception  # noqa: E402

client = TestClient(app)


def test_eval_endpoint_summary():
    d = client.get("/api/eval").json()
    assert d["available"]
    assert d["tamper_model_min"] == 0.9
    assert d["limitations"]
    ab = {r["variant"]: r for r in d["tamper"]["ablation"]}
    assert ab["raw"]["auc"] > 0.9 > 0.6 > ab["jpeg95"]["auc"]
    assert d["tamper"]["real_false_pos"]["raw"][">=0.9"] == 0
    assert d["aigc"]["modes"]["norm"]["real_false_pos@0.5"] == 0


def test_pixel_without_models_falls_back(monkeypatch):
    monkeypatch.setattr(forensics_aigc, "available", lambda: False)
    monkeypatch.setattr(forensics_tamper, "available", lambda: False)
    assert perception.pixel("not_in_fixture.jpg", b"") == (None, "mock")


def test_pixel_low_tamper_score_is_zeroed(monkeypatch):
    monkeypatch.setattr(forensics_aigc, "available", lambda: False)
    monkeypatch.setattr(forensics_tamper, "available", lambda: True)
    monkeypatch.setattr(forensics_tamper, "predict", lambda b: {"score": 0.85, "bbox": [0.1, 0.1, 0.4, 0.4]})
    res, mode = perception.pixel("not_in_fixture.jpg", b"")
    assert mode == "model" and res["tamper"] == 0 and res["bbox"] is None
    monkeypatch.setattr(forensics_tamper, "predict", lambda b: {"score": 0.95, "bbox": [0.1, 0.1, 0.4, 0.4]})
    res, _ = perception.pixel("not_in_fixture.jpg", b"")
    assert res["tamper"] == 0.95 and res["bbox"] == [0.1, 0.1, 0.4, 0.4]


def test_s1_tool_mode_reflects_source():
    res = None
    for kind, p in orchestrator.verify("T1001"):
        if kind == "result":
            res = p
    s1 = next(t for t in res.tools if t.tool == "S1")
    assert s1.mode == "mock"
