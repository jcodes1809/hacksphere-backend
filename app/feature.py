import numpy as np
import pandas as pd

RAW = [
    "ambient_temp_c",
    "humidity_pct",
    "solar_irradiance_wm2"
]

def build_features(df):
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["orig_pos"] = np.arange(len(df))
    df = df.sort_values("timestamp", kind="stable").reset_index(drop=True)

    # Cleaning
    for c in RAW:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.set_index("timestamp")
    df[RAW] = df[RAW].interpolate(
        method="time", limit_direction="both"
    )
    df[RAW] = df[RAW].fillna(df[RAW].median()).fillna(0)
    df["humidity_pct"] = df["humidity_pct"].clip(0, 100)
    df["solar_irradiance_wm2"] = df["solar_irradiance_wm2"].clip(lower=0)
    df = df.reset_index()

    ts = df["timestamp"]
    t = df["ambient_temp_c"]
    h = df["humidity_pct"]
    s = df["solar_irradiance_wm2"]

    # Time features
    df["hour"] = ts.dt.hour
    df["dow"] = ts.dt.dayofweek
    df["is_weekend"] = (df["dow"] >= 5).astype(int)
    df["month"] = ts.dt.month
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["is_peak_window"] = df["hour"].between(18, 22).astype(int)

    # Physics features
    df["cooling_deg"] = np.maximum(0, t - 24)
    df["heating_deg"] = np.maximum(0, 18 - t)
    df["heat_index"] = (
        t + 0.05 * np.maximum(0, h - 40)
        * np.maximum(0, t - 20) / 10
    )
    df["temp_x_hum"] = t * h / 100
    df["solar_x_day"] = s * (
        (df["hour"] >= 6) & (df["hour"] <= 18)
    )

    # Heat memory features
    df["temp_roll3"] = t.rolling(3, min_periods=1).mean()
    df["temp_roll6"] = t.rolling(6, min_periods=1).mean()
    df["temp_lag1"] = t.shift(1).fillna(t)
    df["cooling_roll3"] = df["cooling_deg"].rolling(
        3, min_periods=1
    ).mean()

    return df


FEATURES = [
    "ambient_temp_c", "humidity_pct", "solar_irradiance_wm2",
    "hour", "dow", "is_weekend", "month", "hour_sin", "hour_cos",
    "is_peak_window", "cooling_deg", "heating_deg", "heat_index",
    "temp_x_hum", "solar_x_day", "temp_roll3", "temp_roll6",
    "temp_lag1", "cooling_roll3"
]

