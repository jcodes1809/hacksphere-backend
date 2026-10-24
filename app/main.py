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
from . import quickml, storage
import os
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="HackSphere Microgrid Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"], allow_headers=["*"],
)


class Row(BaseModel):
    timestamp: Optional[str] = None
    ambient_temp_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    solar_irradiance_wm2: Optional[float] = None


class ForecastRequest(BaseModel):
    rows: list[Row]
    temp_offset: Optional[float] = 0.0


def predict_demand(df: pd.DataFrame):
    return quickml.predict(df)


def run_pipeline(df: pd.DataFrame, offset: float):
    try:
        df, report = clean_dataframe(df)
    except CleaningError as e:
        raise HTTPException(status_code=400, detail=str(e))

    df["ambient_temp_c"] = df["ambient_temp_c"] + (offset or 0.0)
    demands, source = predict_demand(df)
    extra = (["Using MOCK predictions (QuickML not connected)."]
             if source == "mock" else [])

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
        "warnings": extra + report_warnings(report) + sim["warnings"],
        "model_source": source,
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
    result = run_pipeline(df, req.temp_offset)
    storage.record_run(result, "forecast")
    return result


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), temp_offset: float = Form(0.0)):
    raw = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read the file as CSV. Check the format.")
    result = run_pipeline(df, temp_offset)
    storage.record_run(result, "upload")
    return result


@app.get("/api/logs")
def logs():
    return storage.get_logs()


@app.get("/api/history")
def history():
    return storage.get_history()
