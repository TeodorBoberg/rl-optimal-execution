import pandas as pd

df = pd.read_csv("data/combined_1m_clean.csv")

n_negative = (df["spread_bps"] < 0).sum()
print(f"Rows with negative spread_bps: {n_negative} / {len(df)} ({n_negative/len(df):.4%})")

if n_negative > 0:
    print("\nWorst offenders (most negative):")
    print(df.nsmallest(10, "spread_bps")[["ticker", "day", "step", "bid", "ask", "spread_bps"]].to_string())
    print("\nBy ticker:")
    print(df[df["spread_bps"] < 0].groupby("ticker").size().to_string())

n_zero_or_neg_close = (df["close"] <= 0).sum()
print(f"\nRows with close <= 0: {n_zero_or_neg_close}")