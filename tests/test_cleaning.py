import io
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from app.cleaning import clean_dataframe, CleaningError
from app.main import app

client = TestClient(app)


def mk(**over):
    d = {"timestamp": ["2015-06-01 00:00:00", "2015-06-01 01:00:00", "2015-06-01 02:00:00"],
         "ambient_temp_c": [30, 31, 32], "humidity_pct": [50, 60, 70],
         "solar_irradiance_wm2": [0, 0, 0]}
    d.update(over)
    return pd.DataFrame(d)


def test_missing_column():
    with pytest.raises(CleaningError):
        clean_dataframe(mk().drop(columns=["humidity_pct"]))


def test_empty():
    with pytest.raises(CleaningError):
        clean_dataframe(mk().iloc[0:0])


def test_sort_and_duplicates():
    df = mk(timestamp=["2015-06-01 02:00:00", "2015-06-01 00:00:00", "2015-06-01 00:00:00"])
    out, rep = clean_dataframe(df)
    assert rep["duplicates_removed"] == 1
    assert out["timestamp"].is_monotonic_increasing


def test_missing_filled():
    out, rep = clean_dataframe(mk(ambient_temp_c=[30, None, 32]))
    assert rep["values_filled"] == 1 and out["ambient_temp_c"][1] == 31


def test_clipping():
    out, rep = clean_dataframe(mk(humidity_pct=[150, 60, 70], solar_irradiance_wm2=[-5, 0, 0]))
    assert out["humidity_pct"].max() <= 100 and out["solar_irradiance_wm2"].min() >= 0
    assert rep["values_clipped"] == 2


def test_bad_timestamp_dropped():
    out, rep = clean_dataframe(mk(timestamp=["junk", "2015-06-01 01:00:00", "2015-06-01 02:00:00"]))
    assert rep["bad_timestamps_dropped"] == 1 and len(out) == 2


def test_upload_ok():
    csv = mk().to_csv(index=False).encode()
    r = client.post("/api/upload", files={"file": ("t.csv", csv, "text/csv")})
    assert r.status_code == 200 and len(r.json()["hours"]) == 3


def test_upload_bad_columns():
    r = client.post("/api/upload", files={"file": ("t.csv", b"a,b\n1,2\n", "text/csv")})
    assert r.status_code == 400


def test_upload_empty_file():
    r = client.post("/api/upload", files={"file": ("t.csv", b"", "text/csv")})
    assert r.status_code == 400
