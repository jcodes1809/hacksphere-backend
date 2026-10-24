"""Input validation and cleaning for telemetry rows."""
import pandas as pd

REQUIRED = ["timestamp", "ambient_temp_c", "humidity_pct", "solar_irradiance_wm2"]
WEATHER = REQUIRED[1:]


class CleaningError(ValueError):
    """Raised with a clear, user-facing message."""


def clean_dataframe(df: pd.DataFrame):
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise CleaningError(f"Missing required column(s): {', '.join(missing)}. Expected: {', '.join(REQUIRED)}")
    if df.empty:
        raise CleaningError("The file has no data rows.")

    df = df[REQUIRED]
    report = {"rows_in": int(len(df)), "rows_dropped": 0, "bad_timestamps_dropped": 0,
              "duplicates_removed": 0, "values_filled": 0, "values_clipped": 0}

    # timestamps
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    bad = int(df["timestamp"].isna().sum())
    df = df.dropna(subset=["timestamp"])
    report["bad_timestamps_dropped"] = bad
    if df.empty:
        raise CleaningError("No valid timestamps found. Use format YYYY-MM-DD HH:MM:SS.")

    # sort + duplicates
    df = df.sort_values("timestamp")
    before = len(df)
    df = df.drop_duplicates(subset="timestamp", keep="first")
    report["duplicates_removed"] = int(before - len(df))

    # numeric + missing values
    for c in WEATHER:
        df[c] = pd.to_numeric(df[c], errors="coerce")
        if df[c].isna().all():
            raise CleaningError(f"Column '{c}' has no valid numbers.")
    nan_before = int(df[WEATHER].isna().sum().sum())
    df = df.set_index("timestamp")
    df[WEATHER] = df[WEATHER].interpolate(method="time", limit_direction="both")
    df = df.reset_index()
    report["values_filled"] = nan_before

    # clip impossible values
    lo = {"ambient_temp_c": -40.0, "humidity_pct": 0.0, "solar_irradiance_wm2": 0.0}
    hi = {"ambient_temp_c": 60.0, "humidity_pct": 100.0, "solar_irradiance_wm2": 1500.0}
    clipped = 0
    for c in WEATHER:
        new = df[c].clip(lower=lo[c], upper=hi[c])
        clipped += int((new != df[c]).sum())
        df[c] = new
    report["values_clipped"] = clipped

    report["rows_dropped"] = report["bad_timestamps_dropped"] + report["duplicates_removed"]
    report["rows_out"] = int(len(df))
    return df.reset_index(drop=True), report


def report_warnings(r: dict) -> list[str]:
    w = []
    if r["bad_timestamps_dropped"]:
        w.append(f"Dropped {r['bad_timestamps_dropped']} row(s) with invalid timestamps.")
    if r["duplicates_removed"]:
        w.append(f"Removed {r['duplicates_removed']} duplicate timestamp(s).")
    if r["values_filled"]:
        w.append(f"Filled {r['values_filled']} missing weather value(s) by time interpolation.")
    if r["values_clipped"]:
        w.append(f"Clipped {r['values_clipped']} out-of-range value(s).")
    return w
