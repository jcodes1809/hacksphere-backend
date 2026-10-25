import numpy as np
import pandas as pd
from app import quickml


def df():
    return pd.DataFrame({
        "timestamp": pd.to_datetime(["2015-07-01 10:00:00", "2015-07-01 11:00:00"]),
        "ambient_temp_c": [35.0, 36.0], "humidity_pct": [50.0, 50.0],
        "solar_irradiance_wm2": [800.0, 900.0]})


def enable(monkeypatch, budget, fake):
    monkeypatch.setenv("QUICKML_ENDPOINT_URL", "http://fake")
    monkeypatch.setenv("QUICKML_CALL_BUDGET", str(budget))
    monkeypatch.setattr(quickml, "call_quickml", fake)


def test_default_never_calls_real(monkeypatch):
    monkeypatch.setenv("QUICKML_ENDPOINT_URL", "http://fake")   # URL set but budget 0
    preds, src = quickml.predict(df())
    assert src == "mock" and len(preds) == 2


def test_no_url_uses_mock(monkeypatch):
    monkeypatch.delenv("QUICKML_ENDPOINT_URL", raising=False)
    monkeypatch.setenv("QUICKML_CALL_BUDGET", "100")
    assert quickml.predict(df())[1] == "mock"


def test_success_then_cached(monkeypatch):
    calls = []
    def fake(feats):
        calls.append(len(feats)); return np.array([150.0, 170.0])
    enable(monkeypatch, 10, fake)
    assert quickml.predict(df()) == ([150.0, 170.0], "quickml")
    assert quickml.predict(df()) == ([150.0, 170.0], "quickml-cached")
    assert calls == [2] and quickml.status()["calls_used"] == 2


def test_budget_too_small_blocks(monkeypatch):
    enable(monkeypatch, 1, lambda f: np.array([1.0, 2.0]))     # needs 2, has 1
    assert quickml.predict(df())[1] == "mock"
    assert quickml.status()["calls_used"] == 0


def test_budget_runs_out(monkeypatch):
    enable(monkeypatch, 2, lambda f: np.array([150.0, 170.0]))
    assert quickml.predict(df())[1] == "quickml"
    other = df(); other["ambient_temp_c"] = [40.0, 41.0]       # new input, budget spent
    assert quickml.predict(other)[1] == "mock"


def test_failure_falls_back_and_still_counts(monkeypatch):
    def boom(f): raise RuntimeError("down")
    enable(monkeypatch, 10, boom)
    assert quickml.predict(df())[1] == "mock"
    assert quickml.status()["calls_used"] == 2


def test_wrong_length_falls_back(monkeypatch):
    enable(monkeypatch, 10, lambda f: np.array([1.0]))
    assert quickml.predict(df())[1] == "mock"
