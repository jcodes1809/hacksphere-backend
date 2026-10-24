import pandas as pd
from fastapi.testclient import TestClient
from app import storage
from app.main import app

client = TestClient(app)


def sample_rows():
    return [{"timestamp": f"2015-07-01 {h:02d}:00:00", "ambient_temp_c": 20 + h,
             "humidity_pct": 50, "solar_irradiance_wm2": 0} for h in range(24)]


def test_history_and_logs_after_forecast():
    storage.reset()
    assert client.get("/api/history").json() == []
    r = client.post("/api/forecast", json={"rows": sample_rows()})
    assert r.status_code == 200
    hist = client.get("/api/history").json()
    assert len(hist) == 1 and {"id", "time", "peak_kw", "overload_count"} <= set(hist[0])
    logs = client.get("/api/logs").json()
    assert logs and {"time", "type", "message"} <= set(logs[0])
    assert any(l["type"] == "mode_switch" for l in logs)


def test_history_newest_first():
    storage.reset()
    client.post("/api/forecast", json={"rows": sample_rows()})
    client.post("/api/forecast", json={"rows": sample_rows(), "temp_offset": 5})
    ids = [h["id"] for h in client.get("/api/history").json()]
    assert ids == sorted(ids, reverse=True) and len(ids) == 2


def test_failed_request_not_recorded():
    storage.reset()
    client.post("/api/upload", files={"file": ("t.csv", b"a,b\n1,2\n", "text/csv")})
    assert client.get("/api/history").json() == []
