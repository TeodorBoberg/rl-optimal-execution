import pandas as pd

df = pd.read_csv("data/combined_1m.csv")

zero_vol_frac = (df["volume"] == 0).mean()
print(f"Fraction of ALL minutes with exactly zero volume: {zero_vol_frac:.1%}")
print()
print("Zero-volume fraction by ticker:")
print(df.groupby("ticker").apply(lambda g: (g["volume"] == 0).mean()).sort_values(ascending=False).to_string())
print()
print("Zero-volume fraction by time-of-day bucket:")
df["step_bucket"] = pd.cut(df["step"], bins=[0, 30, 60, 150, 240, 330, 360, 390], include_lowest=True)
print(df.groupby("step_bucket", observed=True).apply(lambda g: (g["volume"] == 0).mean()).to_string())