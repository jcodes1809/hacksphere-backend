"""QuickML client with QUOTA PROTECTION.
The free QuickML quota is used up (1 call per forecast row). The real endpoint is called
ONLY when BOTH are true: QUICKML_ENDPOINT_URL is set AND QUICKML_CALL_BUDGET > 0.
Default budget is 0, so by default the real endpoint is NEVER called.
Real results are cached, so the same input never costs calls twice."""
import hashlib
import os
import threading

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()  # must run before ml_predict reads its env vars

from .feature import build_features  # noqa: E402
from .ml_predict import _backup_guess, call_quickml  # noqa: E402

_lock = threading.Lock()
_cache = {}
_calls_used = 0
COLS = ["timestamp", "ambient_temp_c", "humidity_pct", "solar_irradiance_wm2"]


def call_budget() -> int:
    try:
        return max(0, int(os.getenv("QUICKML_CALL_BUDGET", "0") or 0))
    except ValueError:
        return 0


def status() -> dict:
    with _lock:
        return {"live_enabled": call_budget() > 0 and os.getenv("QUICKML_ENDPOINT_URL", "").startswith("http"),
                "call_budget": call_budget(), "calls_used": _calls_used,
                "cached_forecasts": len(_cache)}


def reset() -> None:
    global _calls_used
    with _lock:
        _cache.clear()
        _calls_used = 0


def _key(df: pd.DataFrame) -> str:
    d = df[COLS].copy()
    d[COLS[1:]] = d[COLS[1:]].round(3)
    return hashlib.sha256(d.to_csv(index=False).encode()).hexdigest()


def mock_predict(df: pd.DataFrame) -> list:
    return [round(float(x), 2) for x in _backup_guess(df)]


def predict(df: pd.DataFrame):
    """Returns (predictions, source): 'quickml', 'quickml-cached' or 'mock'."""
    global _calls_used
    key, n = _key(df), len(df)
    with _lock:
        if key in _cache:
            return list(_cache[key]), "quickml-cached"
        url = os.getenv("QUICKML_ENDPOINT_URL", "").strip()
        allowed = url.startswith("http") and _calls_used + n <= call_budget()
        if allowed:
            _calls_used += n          # reserve BEFORE calling, so failures still count
    if not allowed:
        return mock_predict(df), "mock"
    try:
        feats = build_features(df)
        sorted_preds = np.asarray(call_quickml(feats), dtype=float)
        if len(sorted_preds) != n:
            raise ValueError(f"expected {n} predictions, got {len(sorted_preds)}")
        out = np.empty(n)
        out[feats["orig_pos"].values] = sorted_preds
        preds = [round(float(x), 2) for x in out]
        with _lock:
            _cache[key] = preds
        return list(preds), "quickml"
    except Exception as e:
        print(f"Warning: QuickML call failed ({e}). Using demo fallback.")
        return mock_predict(df), "mock"
