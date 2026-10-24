"""All tunable assumptions live here (document these in the README)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class GridConfig:
    renewable_threshold_kw: float = 160.0   # demand > this -> Renewable
    overload_threshold_kw: float = 200.0    # demand >= this -> critical alert
    peak_start_hour: int = 18
    peak_end_hour: int = 22                 # inclusive (22:00-22:59 counts)


@dataclass(frozen=True)
class BatteryConfig:
    capacity_kwh: float = 400.0
    initial_soc_pct: float = 80.0
    min_soc_pct: float = 10.0
    max_soc_pct: float = 100.0
    efficiency: float = 0.90                # applied on both charge and discharge
    max_power_kw: float = 150.0
    low_soc_pct: float = 20.0               # "battery low" warning level
    pv_capacity_kw: float = 100.0           # ASSUMPTION: solar kW at 1000 W/m2
    grid_charge_kw: float = 50.0            # ASSUMPTION: extra charging from grid
    co2_kg_per_kwh: float = 0.82            # India grid average (assumption)


GRID = GridConfig()
BATTERY = BatteryConfig()
