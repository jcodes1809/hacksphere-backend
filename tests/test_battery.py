from datetime import datetime, timedelta
from app.battery import simulate


def mk(n, mode, demand=150.0, solar=0.0, start_hour=0):
    base = datetime(2015, 6, 1, start_hour)
    return [{"timestamp": base + timedelta(hours=i), "demand_kw": demand,
             "mode": mode, "solar_wm2": solar} for i in range(n)]


def test_soc_stays_in_limits_when_draining():
    r = simulate(mk(10, "Renewable"))
    assert min(r["soc_pct"]) >= 10.0 and r["warnings"]


def test_soc_never_exceeds_100():
    r = simulate(mk(24, "Main Grid", solar=1000))
    assert max(r["soc_pct"]) <= 100.0


def test_first_hour_discharge_math():
    r = simulate(mk(1, "Renewable", demand=90.0))
    assert r["soc_pct"][0] == 55.0   # 320 kWh - 90/0.9 = 220 kWh = 55%
