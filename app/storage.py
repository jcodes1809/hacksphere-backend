"""Run history + event log.
Always keeps an in-memory copy (fast, never fails) and does a best-effort write-through to
Catalyst: Data Store tables forecast_runs / event_logs, and Stratus bucket uploads/ for CSVs.
A Catalyst failure NEVER breaks an API response; it is reported in result["saved"] and /api/storage."""
import os
import re
import threading
import time
from datetime import datetime
from itertools import count

_lock = threading.Lock()
_ids = count(1)
_runs: list = []
_logs: list = []
MAX_ITEMS = 1000
MAX_LOG_ROWS_PER_RUN = 25      # Data Store dev limit is 5000 rows per table
MAX_TEXT = 250
_diag = {"datastore": "not tried", "stratus": "not tried", "last_error": None}
_fail = {"n": 0, "t": 0.0}


def _bucket() -> str:
    return os.getenv("STRATUS_BUCKET", "gridpilot-storage")


def _runs_table() -> str:
    return os.getenv("DATASTORE_RUNS_TABLE", "forecast_runs")


def _logs_table() -> str:
    return os.getenv("DATASTORE_LOGS_TABLE", "event_logs")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ev(run_id, time_, type_, message):
    return {"run_id": run_id, "time": time_, "type": type_, "message": message}


def _catalyst_app(http):
    """Init the Catalyst SDK from the incoming request (required in AppSail)."""
    if http is None or os.getenv("CATALYST_STORAGE", "1") == "0":
        return None
    import zcatalyst_sdk          # ImportError if the SDK is not bundled
    return zcatalyst_sdk.initialize(req=http)


def _paused() -> bool:
    return _fail["n"] >= 3 and time.time() - _fail["t"] < 300


def _write_datastore(app, run_row: dict, log_rows: list) -> None:
    ds = app.datastore()
    ds.table(_runs_table()).insert_row(run_row)
    if log_rows:
        t = ds.table(_logs_table())
        if hasattr(t, "insert_rows"):
            t.insert_rows(log_rows)
        else:
            for r in log_rows:
                t.insert_row(r)


def _write_stratus(app, run_id: int, raw: bytes, filename) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename or "upload.csv")[-60:]
    key = f"uploads/{datetime.now():%Y%m%d-%H%M%S}_run{run_id}_{safe}"
    app.stratus().bucket(_bucket()).put_object(key, raw.decode("utf-8", errors="replace"))
    return key


def record_run(result: dict, source: str, http=None, raw: bytes = None, filename: str = None) -> dict:
    s = result["summary"]
    switches, overloads, warns = [], [], []
    with _lock:
        run_id = next(_ids)
        run_time = _now()
        prev = None
        for h in result["hours"]:
            t = h["timestamp"].isoformat()
            hhmm = h["timestamp"].strftime("%H:%M")
            if prev is not None and h["mode"] != prev:
                switches.append(_ev(run_id, t, "mode_switch", f"Switched {prev} -> {h['mode']} at {hhmm}"))
            if h["overload"]:
                overloads.append(_ev(run_id, t, "overload", f"Critical overload: {h['demand_kw']} kW at {hhmm}"))
            prev = h["mode"]
        for w in result["warnings"]:
            warns.append(_ev(run_id, run_time, "warning", w))
        run_ev = _ev(run_id, run_time, "run", f"{source} run #{run_id}: peak {s['peak_kw']} kW, "
                                              f"{s['overload_count']} overload hour(s)")
        _runs.append({"id": run_id, "time": run_time, "source": source,
                      "peak_kw": s["peak_kw"], "overload_count": s["overload_count"]})
        _logs.extend(switches + overloads + warns + [run_ev])
        del _runs[:-MAX_ITEMS]
        del _logs[:-MAX_ITEMS]

    saved = {"run_id": run_id, "datastore": False, "stratus": False}
    try:
        app = _catalyst_app(http)
    except Exception as e:
        app, _diag["last_error"] = None, f"SDK init failed: {type(e).__name__}: {e}"
        _diag["datastore"] = _diag["stratus"] = "sdk init failed"
    if app is None:
        saved["note"] = "Catalyst storage not active (local run, disabled, or SDK init failed)"
        return saved
    if _paused():
        saved["note"] = "Catalyst storage paused after repeated failures (retries in 5 minutes)"
        return saved

    # compact rows for Data Store (stay far below the 5000-row dev limit)
    compact = [run_ev] + warns[:5] + switches[:10]
    if overloads:
        hours = ", ".join(e["message"].rsplit(" at ", 1)[-1] for e in overloads[:8])
        compact.append(_ev(run_id, run_time, "overload",
                           f"{len(overloads)} critical overload hour(s): {hours}"))
    log_rows = [{"run_id": run_id, "event_time": e["time"][:40], "type": e["type"],
                 "message": e["message"][:MAX_TEXT]} for e in compact[:MAX_LOG_ROWS_PER_RUN]]
    run_row = {"run_id": run_id, "run_time": run_time, "source": source,
               "peak_kw": float(s["peak_kw"]), "overload_count": int(s["overload_count"]),
               "model_source": str(result.get("model_source", ""))}
    try:
        _write_datastore(app, run_row, log_rows)
        saved["datastore"], _diag["datastore"] = True, "ok"
        _fail["n"] = 0
    except Exception as e:
        _fail["n"] += 1; _fail["t"] = time.time()
        _diag["datastore"] = "error"; _diag["last_error"] = f"Data Store: {type(e).__name__}: {e}"
    if raw is not None:
        try:
            saved["stratus_key"] = _write_stratus(app, run_id, raw, filename)
            saved["stratus"], _diag["stratus"] = True, "ok"
        except Exception as e:
            _diag["stratus"] = "error"; _diag["last_error"] = f"Stratus: {type(e).__name__}: {e}"
    return saved


def diagnostics() -> dict:
    return {**_diag, "bucket": _bucket(), "runs_table": _runs_table(), "logs_table": _logs_table(),
            "consecutive_failures": _fail["n"]}


def get_history() -> list:
    with _lock:
        return list(reversed(_runs))


def get_logs() -> list:
    with _lock:
        return list(reversed(_logs))


def reset() -> None:
    with _lock:
        _runs.clear()
        _logs.clear()
    _diag.update({"datastore": "not tried", "stratus": "not tried", "last_error": None})
    _fail.update({"n": 0, "t": 0.0})
