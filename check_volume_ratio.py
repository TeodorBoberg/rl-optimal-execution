import pandas as pd

df = pd.read_csv("data/combined_1m.csv")
avg_vol_per_step = df.groupby("ticker")["volume"].sum() / (df.groupby("ticker")["day"].nunique() * 390)
df["avg_vol_per_step"] = df["ticker"].map(avg_vol_per_step)
df["vol_ratio"] = df["volume"] / df["avg_vol_per_step"]

print("Per-minute volume as a fraction of avg_vol_per_step:")
print(df["vol_ratio"].describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]))
print()
print("Fraction of minutes with volume < 25% of avg_vol_per_step:", (df["vol_ratio"] < 0.25).mean())
print("Fraction of minutes with volume < 10% of avg_vol_per_step:", (df["vol_ratio"] < 0.10).mean())
print()

df["step_bucket"] = pd.cut(df["step"], bins=[0, 30, 60, 150, 240, 330, 360, 390], include_lowest=True)
print("Median vol_ratio by time-of-day bucket (checks the U-shape hypothesis):")
print(df.groupby("step_bucket", observed=True)["vol_ratio"].median())