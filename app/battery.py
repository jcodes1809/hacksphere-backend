"""Hour-by-hour battery state-of-charge simulation (1-hour steps)."""
from .config import BATTERY, BatteryConfig, GRID
from .controller import RENEWABLE


def simulate(hours: list[dict], cfg: BatteryConfig = BATTERY) -> dict:
    """hours: dicts with timestamp(datetime), demand_kw, mode, solar_wm2.
    Returns soc list, warnings, and kWh supplied by the battery."""
    cap = cfg.capacity_kwh
    min_kwh = cap * cfg.min_soc_pct / 100
    max_kwh = cap * cfg.max_soc_pct / 100
    soc_kwh = cap * cfg.initial_soc_pct / 100

    soc_list, warnings, supplied_kwh = [], [], 0.0

    for h in hours:
        hour = h["timestamp"].hour
        label = h["timestamp"].strftime("%H:%M")
        in_window = GRID.peak_start_hour <= hour <= GRID.peak_end_hour

        if h["mode"] == RENEWABLE:
            want_kw = min(h["demand_kw"], cfg.max_power_kw)
            avail_kw = max(0.0, (soc_kwh - min_kwh) * cfg.efficiency)
            delivered = min(want_kw, avail_kw)
            soc_kwh -= delivered / cfg.efficiency
            supplied_kwh += delivered
            if delivered < want_kw - 1e-9:
                warnings.append(f"Battery empty at {label}: cannot fully cover demand. Start charging earlier.")
        else:
            solar_kw = max(0.0, h["solar_wm2"]) / 1000 * cfg.pv_capacity_kw
            charge_kw = min(cfg.max_power_kw, solar_kw + cfg.grid_charge_kw)
            room_kw = (max_kwh - soc_kwh) / cfg.efficiency
            charge_kw = max(0.0, min(charge_kw, room_kw))
            soc_kwh += charge_kw * cfg.efficiency

        soc_pct = round(soc_kwh / cap * 100, 1)
        soc_list.append(soc_pct)

        if soc_pct < cfg.low_soc_pct and not any(f"at {label}" in w for w in warnings):
            warnings.append(f"Battery low ({soc_pct}%) at {label}.")
        if in_window and soc_kwh <= min_kwh + 1e-6 and not any(f"empty at {label}" in w for w in warnings):
            warnings.append(f"Battery will run empty at {label} during the evening peak. Start charging earlier.")

    return {"soc_pct": soc_list, "warnings": warnings, "supplied_kwh": supplied_kwh}
