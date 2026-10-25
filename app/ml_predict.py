import argparse
import os
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests

from .feature import build_features, FEATURES

QUICKML_ENDPOINT_URL = os.getenv("QUICKML_ENDPOINT_URL", "YOUR_PUBLISHED_QUICKML_ENDPOINT_URL_HERE")
ENDPOINT_KEY   = os.getenv("QUICKML_ENDPOINT_KEY", "")
CATALYST_ORG   = os.getenv("CATALYST_ORG", "")
QUICKML_ENV    = os.getenv("QUICKML_ENV", "Development")
ACCOUNTS_URL   = os.getenv("ZOHO_ACCOUNTS_URL", "https://accounts.zoho.in")
CLIENT_ID      = os.getenv("ZOHO_CLIENT_ID", "")
CLIENT_SECRET  = os.getenv("ZOHO_CLIENT_SECRET", "")
REFRESH_TOKEN  = os.getenv("ZOHO_REFRESH_TOKEN", "")

_token = {"value": None, "time": 0}


def get_access_token():
    if _token["value"] and time.time() - _token["time"] < 50 * 60:
        return _token["value"]
    r = requests.post(
        f"{ACCOUNTS_URL}/oauth/v2/token",
        data={"refresh_token": REFRESH_TOKEN, "client_id": CLIENT_ID,
              "client_secret": CLIENT_SECRET, "grant_type": "refresh_token"},
        timeout=20,
    )
    if r.status_code != 200 or "access_token" not in r.json():
        raise RuntimeError(f"token refresh {r.status_code}: {r.text[:150]}")
    _token["value"] = r.json()["access_token"]
    _token["time"] = time.time()
    return _token["value"]


def _find_number(obj):
    if isinstance(obj, bool):
        return None
    if isinstance(obj, (int, float)):
        return float(obj)
    if isinstance(obj, str):
        try:
            return float(obj)
        except ValueError:
            return None
    if isinstance(obj, dict):
        for k, v in obj.items():
            if "target_demand" in str(k).lower():
                n = _find_number(v)
                if n is not None:
                    return n
        for v in obj.values():
            n = _find_number(v)
            if n is not None:
                return n
    if isinstance(obj, list):
        for v in obj:
            n = _find_number(v)
            if n is not None:
                return n
    return None


def _call_one(record):
    headers = {
        "Authorization": f"Zoho-oauthtoken {get_access_token()}",
        "X-QUICKML-ENDPOINT-KEY": ENDPOINT_KEY,
        "CATALYST-ORG": CATALYST_ORG,
        "Environment": QUICKML_ENV,
        "Content-Type": "application/json",
    }
    for attempt in range(3):
        try:
            r = requests.post(QUICKML_ENDPOINT_URL, json={"data": record}, headers=headers, timeout=30)
            r.raise_for_status()
            n = _find_number(r.json().get("result", r.json()))
            if n is None:
                raise ValueError(f"No number in response: {r.text[:200]}")
            return n
        except Exception as e:
            if "403" in str(e) or "401" in str(e) or attempt == 2:
                raise
            time.sleep(1.5)


def call_quickml(feature_df):
    records = feature_df[FEATURES].astype(float).to_dict(orient="records")
    get_access_token()  # get ONE token before the threads start
    with ThreadPoolExecutor(max_workers=8) as ex:
        return np.array(list(ex.map(_call_one, records)), dtype=float)


def _backup_guess(df):
    hours = pd.to_datetime(df["timestamp"]).dt.hour
    base = 120.0 + 30.0 * np.sin(2 * np.pi * (hours - 6) / 24)
    return (base + np.maximum(0.0, df["ambient_temp_c"] - 24.0) * 8.5).values


def predict(input_df: pd.DataFrame):
    feats = build_features(input_df)
    if QUICKML_ENDPOINT_URL.startswith("http"):
        try:
            preds_sorted = call_quickml(feats)
            out = np.empty(len(feats))
            out[feats["orig_pos"].values] = preds_sorted
            print("[predict] Source: QuickML endpoint OK")
            return out
        except Exception as e:
            print(f"[predict] !!! QuickML call FAILED ({e}). Using backup guess - FIX THIS !!!")
    else:
        print("[predict] !!! Endpoint URL not set. Using backup guess - FIX THIS !!!")
    return np.array(_backup_guess(input_df), dtype=float)



_orig_get_access_token = get_access_token


def get_access_token():
    import json
    f = ".zoho_token_cache.json"
    try:
        c = json.load(open(f))
        if time.time() - c["time"] < 50 * 60 and c.get("rt") == REFRESH_TOKEN[-8:]:
            return c["value"]
    except Exception:
        pass
    t = _orig_get_access_token()
    try:
        json.dump({"value": t, "time": time.time(), "rt": REFRESH_TOKEN[-8:]}, open(f, "w"))
    except Exception:
        pass
    return t


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="sample_test_input.csv")
    ap.add_argument("--output", default="predictions.csv")
    args = ap.parse_args()
    df = pd.read_csv(args.input)
    preds = predict(df)
    pd.DataFrame({"timestamp": df["timestamp"], "target_demand_kw": np.round(preds, 2)}).to_csv(args.output, index=False)
    print(f"Saved {len(preds)} predictions to {args.output}")
