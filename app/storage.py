"""In-memory run history and event log.
Later: swap these functions for Catalyst Data Store calls (same signatures)."""
import threading
from datetime import datetime
from itertools import count

_lock = threading.Lock()
_ids = count(1)
_runs: list[dict] = []
_logs: list[dict] = []
MAX_ITEMS = 1000


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _log(run_id: int, time: str, type_: str, message: str) -> None:
    _logs.append({"run_id": run_id, "time": time, "type": type_, "message": message})


def record_run(result: dict, source: str) -> int:
    s = result["summary"]
    with _lock:
        run_id = next(_ids)
        _runs.append({"id": run_id, "time": _now(), "source": source,
                      "peak_kw": s["peak_kw"], "overload_count": s["overload_count"]})
        prev_mode = None
        for h in result["hours"]:
            t = h["timestamp"].isoformat()
            hhmm = h["timestamp"].strftime("%H:%M")
            if prev_mode is not None and h["mode"] != prev_mode:
                _log(run_id, t, "mode_switch", f"Switched {prev_mode} -> {h['mode']} at {hhmm}")
            if h["overload"]:
                _log(run_id, t, "overload", f"Critical overload: {h['demand_kw']} kW at {hhmm}")
            prev_mode = h["mode"]
        for w in result["warnings"]:
            _log(run_id, _now(), "warning", w)
        _log(run_id, _now(), "run", f"{source} run #{run_id}: peak {s['peak_kw']} kW, "
                                     f"{s['overload_count']} overload hour(s)")
        del _runs[:-MAX_ITEMS]
        del _logs[:-MAX_ITEMS]
    return run_id


def get_history() -> list[dict]:
    with _lock:
        return list(reversed(_runs))   # newest first


def get_logs() -> list[dict]:
    with _lock:
        return list(reversed(_logs))   # newest first


def reset() -> None:
    with _lock:
        _runs.clear()
        _logs.clear()
