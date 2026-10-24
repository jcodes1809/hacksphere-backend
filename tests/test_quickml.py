import pandas as pd
from app import quickml


def df():
    return pd.DataFrame({
        "timestamp": pd.to_datetime(["2015-07-01 10:00:00", "2015-07-01 11:00:00"]),
        "ambient_temp_c": [35.0, 36.0], "humidity_pct": [50.0, 50.0],
        "solar_irradiance_wm2": [800.0, 900.0]})


class FakeResp:
    def __init__(self, data): self._d = data
    def raise_for_status(self): pass
    def json(self): return self._d


def test_no_env_uses_mock(monkeypatch):
    monkeypatch.delenv("QUICKML_ENDPOINT_URL", raising=False)
    preds, src = quickml.predict(df())
    assert src == "mock" and len(preds) == 2


def test_quickml_success(monkeypatch):
    monkeypatch.setenv("QUICKML_ENDPOINT_URL", "http://fake")
    monkeypatch.setattr(quickml.requests, "post", lambda *a, **k: FakeResp({"predictions": [150, 170]}))
    assert quickml.predict(df()) == ([150.0, 170.0], "quickml")


def test_quickml_failure_falls_back(monkeypatch):
    monkeypatch.setenv("QUICKML_ENDPOINT_URL", "http://fake")
    def boom(*a, **k): raise RuntimeError("down")
    monkeypatch.setattr(quickml.requests, "post", boom)
    assert quickml.predict(df())[1] == "mock"


def test_wrong_length_falls_back(monkeypatch):
    monkeypatch.setenv("QUICKML_ENDPOINT_URL", "http://fake")
    monkeypatch.setattr(quickml.requests, "post", lambda *a, **k: FakeResp({"predictions": [1]}))
    assert quickml.predict(df())[1] == "mock"
