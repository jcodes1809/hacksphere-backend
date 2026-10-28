import pandas as pd, os
os.makedirs("demo_data", exist_ok=True)
ts = pd.date_range("2015-07-01", periods=24, freq="h")
def day(temp, hum=55):
    return pd.DataFrame({"timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
        "ambient_temp_c": [temp + (3 if 11 <= h <= 16 else 0) for h in range(24)],
        "humidity_pct": hum,
        "solar_irradiance_wm2": [max(0, int(900 - abs(h - 13) * 140)) if 6 <= h <= 19 else 0 for h in range(24)]})
day(33).to_csv("demo_data/normal_day.csv", index=False)
day(44, 40).to_csv("demo_data/heatwave_day.csv", index=False)
day(18, 70).to_csv("demo_data/cool_day.csv", index=False)
m = day(33); m.loc[[5, 6, 15], "ambient_temp_c"] = None; m.loc[10, "humidity_pct"] = 150
m.to_csv("demo_data/missing_values.csv", index=False)
pd.DataFrame({"a": [1], "b": [2]}).to_csv("demo_data/bad_columns.csv", index=False)
print("created:", sorted(os.listdir("demo_data")))
