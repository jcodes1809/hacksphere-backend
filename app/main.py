from datetime import datetime
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from .battery import simulate
from .config import BATTERY
from .controller import decide

app = FastAPI(title="HackSphere Microgrid Backend")


class Row(BaseModel):
    timestamp: datetime
    ambient_temp_c: float
    humidity_pct: float
    solar_irradiance_wm2: float


class ForecastRequest(BaseModel):
    rows: list[Row]
    temp_offset: Optional[float] = 0.0


def mock_predict(row: Row, offset: float) -> float:
    """TEMPORARY: replaced by QuickML in Step 6."""
    t = row.ambient_temp_c + offset
    evening = 25 if 17 <= row.timestamp.hour <= 22 else 0
    return round(max(50.0, 60 + 4.5 * max(0, t - 20) + evening - 0.02 * row.solar_irradiance_wm2), 2)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/forecast")
def forecast(req: ForecastRequest):
    rows = sorted(req.rows, key=lambda r: r.timestamp)
    hours = []
    for r in rows:
        d = mock_predict(r, req.temp_offset or 0.0)
        ctl = decide(d, r.timestamp.hour)
        # DEMO band only: +/-10%, NOT a statistical confidence interval
        hours.append({"timestamp": r.timestamp, "demand_kw": d,
                      "low_kw": round(d * 0.9, 2), "high_kw": round(d * 1.1, 2),
                      "solar_wm2": r.solar_irradiance_wm2, **ctl})

    sim = simulate(hours)
    for h, soc in zip(hours, sim["soc_pct"]):
        h["soc_pct"] = soc
        h.pop("solar_wm2")

    peak = max(hours, key=lambda h: h["demand_kw"]) if hours else None
    return {
        "hours": hours,
        "summary": {
            "peak_kw": peak["demand_kw"] if peak else None,
            "peak_hour": peak["timestamp"].strftime("%H:%M") if peak else None,
            "overload_count": sum(h["overload"] for h in hours),
            "co2_saved": round(sim["supplied_kwh"] * BATTERY.co2_kg_per_kwh, 2),
        },
        "warnings": sim["warnings"],
    }
