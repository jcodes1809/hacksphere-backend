import io
from datetime import datetime
from typing import Optional

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .battery import simulate
from .cleaning import CleaningError, clean_dataframe, report_warnings
from .config import BATTERY
from .controller import decide

app = FastAPI(title="HackSphere Microgrid Backend")


class Row(BaseModel):
    timestamp: Optional[str] = None
    ambient_temp_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    solar_irradiance_wm2: Optional[float] = None


class ForecastRequest(BaseModel):
    rows: list[Row]
    temp_offset: Optional[float] = 0.0


def predict_demand(df: pd.DataFrame) -> list[float]:
    """TEMPORARY mock. Step 6 replaces this with the QuickML call."""
    out = []
    for r in df.itertuples():
        evening = 25 if 17 <= r.timestamp.hour <= 22 else 0
        out.append(round(max(50.0, 60 + 4.5 * max(0, r.ambient_temp_c - 20) + evening
                             - 0.02 * r.solar_irradiance_wm2), 2))
    return out


def run_pipeline(df: pd.DataFrame, offset: float):
    try:
        df, report = clean_dataframe(df)
    except CleaningError as e:
        raise HTTPException(status_code=400, detail=str(e))

    df["ambient_temp_c"] = df["ambient_temp_c"] + (offset or 0.0)
    demands = predict_demand(df)

    hours = []
    for r, d in zip(df.itertuples(), demands):
        ts = r.timestamp.to_pydatetime()
        # DEMO band only (+/-10%): NOT a statistical confidence interval
        hours.append({"timestamp": ts, "demand_kw": d,
                      "low_kw": round(d * 0.9, 2), "high_kw": round(d * 1.1, 2),
                      "solar_wm2": r.solar_irradiance_wm2, **decide(d, ts.hour)})

    sim = simulate(hours)
    for h, soc in zip(hours, sim["soc_pct"]):
        h["soc_pct"] = soc
        h.pop("solar_wm2")

    peak = max(hours, key=lambda h: h["demand_kw"])
    return {
        "hours": hours,
        "summary": {
            "peak_kw": peak["demand_kw"],
            "peak_hour": peak["timestamp"].strftime("%H:%M"),
            "overload_count": sum(h["overload"] for h in hours),
            "co2_saved": round(sim["supplied_kwh"] * BATTERY.co2_kg_per_kwh, 2),
        },
        "warnings": report_warnings(report) + sim["warnings"],
        "cleaning_report": report,
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/forecast")
def forecast(req: ForecastRequest):
    if not req.rows:
        raise HTTPException(status_code=400, detail="No rows provided.")
    df = pd.DataFrame([r.model_dump() for r in req.rows])
    return run_pipeline(df, req.temp_offset)


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), temp_offset: float = Form(0.0)):
    raw = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read the file as CSV. Check the format.")
    return run_pipeline(df, temp_offset)
