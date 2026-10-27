from datetime import datetime, timedelta
import pytest
from app import storage


def result():
    base = datetime(2015, 7, 1)
    hours = []
    for i in range(24):
        d = 210.0 if 10 <= i <= 20 else 120.0
        hours.append({"timestamp": base + timedelta(hours=i), "demand_kw": d,
                      "mode": "Renewable" if (d > 160 or 18 <= i <= 22) else "Main Grid",
                      "overload": d >= 200})
    return {"hours": hours, "summary": {"peak_kw": 210.0, "overload_count": 11},
            "warnings": [f"w{i}" for i in range(8)], "model_source": "mock"}


class T:
    def __init__(s): s.rows = []
    def insert_row(s, r): s.rows.append(r)
    def insert_rows(s, rs): s.rows.extend(rs)

class DS:
    def __init__(s): s.t = {}
    def table(s, n): return s.t.setdefault(n, T())

class B:
    def __init__(s): s.objs = {}
    def put_object(s, k, d): s.objs[k] = d

class ST:
    def __init__(s): s.b = B()
    def bucket(s, n): return s.b

class App:
    def __init__(s): s.d, s.s = DS(), ST()
    def datastore(s): return s.d
    def stratus(s): return s.s


def test_write_through(monkeypatch):
    storage.reset()
    app = App()
    monkeypatch.setattr(storage, "_catalyst_app", lambda http: app)
    saved = storage.record_run(result(), "upload", http=object(), raw=b"a,b\n1,2\n", filename="my data.csv")
    assert saved["datastore"] and saved["stratus"] and saved["stratus_key"].startswith("uploads/")
    assert len(app.d.t["forecast_runs"].rows) == 1
    logs = app.d.t["event_logs"].rows
    assert 1 < len(logs) <= 25 and all(len(r["message"]) <= 250 for r in logs)
    assert app.s.b.objs[saved["stratus_key"]] == "a,b\n1,2\n"
    assert len([l for l in storage.get_logs() if l["type"] == "overload"]) == 11


def test_no_http_is_memory_only():
    storage.reset()
    s = storage.record_run(result(), "forecast")
    assert s["datastore"] is False and "note" in s and len(storage.get_history()) == 1


def test_failure_never_raises_and_pauses(monkeypatch):
    storage.reset()
    class Bad(App):
        def datastore(s): raise RuntimeError("table missing")
    monkeypatch.setattr(storage, "_catalyst_app", lambda http: Bad())
    for _ in range(3):
        assert storage.record_run(result(), "forecast", http=object())["datastore"] is False
    assert "paused" in storage.record_run(result(), "forecast", http=object())["note"]
    assert "table missing" in storage.diagnostics()["last_error"]
