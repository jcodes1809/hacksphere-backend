# Backend (P2): API, controller, battery simulation

Run: `uvicorn app.main:app --reload`   Test: `python -m pytest -q`
Env vars (see `.env.example`): QUICKML_ENDPOINT_URL, QUICKML_TOKEN, CORS_ORIGINS.
Never commit real tokens. If QUICKML_ENDPOINT_URL is empty, the API uses mock predictions
and says so in `warnings` and `model_source`.

## Switching rules (from the problem statement)
- Renewable if demand > 160 kW OR hour in 18..22 (22:00-22:59 included); else Main Grid.
- Exactly 160 kW outside the window = Main Grid.
- Critical overload if demand >= 200 kW, independent of mode.

## Assumptions (all in `app/config.py`, not measured data)
| Item | Value |
|---|---|
| Battery capacity | 400 kWh |
| Initial / min / max SoC | 80% / 10% / 100% |
| Efficiency | 90% (applied on both charge and discharge) |
| Max charge/discharge power | 150 kW |
| Low-battery warning | SoC < 20% or empty during 18:00-22:59 |
| Solar array size | 100 kW at 1000 W/m2 (assumed) |
| Extra grid charging in Main Grid mode | 50 kW (assumed) |
| CO2 factor | 0.82 kg/kWh (India grid average, assumed) |
| low/high band | demo +/-10%, NOT a statistical confidence interval |

`co2_saved` = kWh supplied by the battery x 0.82.
