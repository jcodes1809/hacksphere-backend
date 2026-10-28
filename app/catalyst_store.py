"""Best-effort mirror of runs/logs to Catalyst Data Store and uploads to Stratus.
Off unless ENABLE_CLOUD_STORAGE=1. Never raises: failures are recorded in status()."""
import contextvars
import io
import logging
import os
from datetime import datetime

log = logging.getLogger("catalyst_store")
_req = contextvars.ContextVar("catalyst_req", default=None)
_state = {"last_error": None, "runs_saved": 0, "logs_saved": 0, "uploads_saved": 0}


def enabled() -> bool:
    return os.getenv("ENABLE_CLOUD_STORAGE", "0") == "1"


def set_request(request) -> None:
    _req.set(request)


def _app():
    import zcatalyst_sdk  # imported lazily so local dev/tests don't need it
    req = _req.get()
    if req is None:
        raise RuntimeError("no request in context")
    return zcatalyst_sdk.initialize(req=req)


def _fail(where: str, exc: Exception) -> None:
    _state["last_error"] = f"{where}: {type(exc).__name__}: {exc}"
    log.warning("catalyst_store %s", _state["last_error"])


def mirror_run(run: dict, logs: list[dict]) -> None:
    if not enabled():
        return
    try:
        ds = _app().datastore()
        ds.table(os.getenv("DS_RUNS_TABLE", "forecast_runs")).insert_rows([{
            "run_id": run["id"], "run_time": run["time"], "source": run["source"],
            "peak_kw": run["peak_kw"], "overload_count": run["overload_count"],
            "model_source": run.get("model_source", ""),
        }])
        _state["runs_saved"] += 1
        if logs:
            ds.table(os.getenv("DS_LOGS_TABLE", "event_logs")).insert_rows([{
                "run_id": l["run_id"], "event_time": l["time"],
                "type": l["type"], "message": l["message"][:500],
            } for l in logs])
            _state["logs_saved"] += len(logs)
    except Exception as e:  # noqa: BLE001
        _fail("data_store", e)


def _to_body(content):
    """Stratus accepts a string or BufferReader (not BytesIO) and rejects empty bodies."""
    if isinstance(content, (bytes, bytearray)):
        content = bytes(content).decode("utf-8", errors="replace")
    if not content:
        raise ValueError("empty upload body")
    return content


def save_upload(filename: str, content: bytes) -> None:
    bucket_name = os.getenv("STRATUS_BUCKET")
    if not enabled() or not bucket_name:
        return
    try:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe = "".join(c for c in (filename or "upload.csv") if c.isalnum() or c in "._-")
        bucket = _app().stratus().bucket(bucket_name)
        bucket.put_object(f"uploads/{stamp}_{safe}", _to_body(content))
        _state["uploads_saved"] += 1
    except Exception as e:  # noqa: BLE001
        _fail("stratus", e)


def status() -> dict:
    return {"enabled": enabled(), "bucket": os.getenv("STRATUS_BUCKET"), **_state}
