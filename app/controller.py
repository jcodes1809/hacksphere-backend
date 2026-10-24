"""Pure switching rules: easy to unit test."""
from .config import GRID, GridConfig

RENEWABLE = "Renewable"
MAIN_GRID = "Main Grid"


def decide(demand_kw: float, hour: int, cfg: GridConfig = GRID) -> dict:
    in_window = cfg.peak_start_hour <= hour <= cfg.peak_end_hour
    above = demand_kw > cfg.renewable_threshold_kw
    overload = demand_kw >= cfg.overload_threshold_kw

    if above and in_window:
        mode, reason = RENEWABLE, "Demand above 160 kW and evening peak window"
    elif above:
        mode, reason = RENEWABLE, "Demand above 160 kW"
    elif in_window:
        mode, reason = RENEWABLE, "Evening peak window (18:00-22:59)"
    else:
        mode, reason = MAIN_GRID, "Demand at or below 160 kW, outside peak window"

    if overload:
        reason += " | CRITICAL overload (>= 200 kW)"
    return {"mode": mode, "overload": overload, "reason": reason}
