"""QuickML client. Falls back to a mock when no endpoint is set or the call fails.
Env vars: QUICKML_ENDPOINT_URL, QUICKML_TOKEN (optional),
QUICKML_AUTH_HEADER (optional, default 'Authorization: Zoho-oauthtoken {token}')."""
import os

import pandas as pd
import requests


def mock_predict(df: pd.DataFrame) -> list[float]:
    out = []
    for r in df.itertuples():
        evening = 25 if 17 <= r.timestamp.hour <= 22 else 0
        out.append(round(max(50.0, 60 + 4.5 * max(0, r.ambient_temp_c - 20) + evening
                             - 0.02 * r.solar_irradiance_wm2), 2))
    return out


def predict(df: pd.DataFrame) -> tuple[list[float], str]:
    """Returns (predictions, source) where source is 'quickml' or 'mock'."""
    url = os.getenv("QUICKML_ENDPOINT_URL", "").strip()
    if not url:
        return mock_predict(df), "mock"
    try:
        # TODO (when P1 delivers feature.py): add the same features here
        # before sending, e.g. feats = feature.make_features(df)
        feats = df.copy()
        feats["timestamp"] = feats["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
        headers = {}
        token = os.getenv("QUICKML_TOKEN", "").strip()
        if token:
            tpl = os.getenv("QUICKML_AUTH_HEADER", "Authorization: Zoho-oauthtoken {token}")
            name, _, value = tpl.partition(":")
            headers[name.strip()] = value.strip().format(token=token)
        resp = requests.post(url, json={"data": feats.to_dict(orient="records")},
                             headers=headers, timeout=10)
        resp.raise_for_status()
        preds = [float(x) for x in resp.json()["predictions"]]
        if len(preds) != len(df):
            raise ValueError(f"expected {len(df)} predictions, got {len(preds)}")
        return preds, "quickml"
    except Exception as e:
        print(f"Warning: QuickML call failed ({e}). Using mock fallback.")
        return mock_predict(df), "mock"
