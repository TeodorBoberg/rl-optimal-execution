import pandas as pd
import numpy as np
import glob
import os

files_by_ticker = {}
for f in glob.glob("data/tick/*_tbbo_*.csv"):
    symbol = os.path.basename(f).split("_tbbo_")[0].upper()
    files_by_ticker.setdefault(symbol, []).append(f)

results = []
for symbol in sorted(files_by_ticker.keys()):
    df = pd.concat([pd.read_csv(f) for f in files_by_ticker[symbol]], ignore_index=True)
    spread_bps = (df["ask_px_00"] - df["bid_px_00"]) / ((df["ask_px_00"] + df["bid_px_00"]) / 2) * 10_000
    median_spread = spread_bps.median()
    frac_over_100 = (spread_bps > 100).mean()
    results.append({
        "ticker": symbol,
        "median_spread_bps": median_spread,
        "frac_over_100bps": frac_over_100,
        "n_ticks": len(df),
    })

summary = pd.DataFrame(results).sort_values("median_spread_bps")
print(summary.to_string(index=False))
print()

# Simple, defensible threshold: a real US large/mid-cap equity essentially
# never has a median spread over 20bps during regular hours. Anything above
# that is almost certainly a coverage artifact of EQUS.MINI's blended-venue
# composite for that specific name, not a real market spread.
RELIABLE_THRESHOLD_BPS = 20.0
reliable = summary[summary["median_spread_bps"] <= RELIABLE_THRESHOLD_BPS]
unreliable = summary[summary["median_spread_bps"] > RELIABLE_THRESHOLD_BPS]

print(f"Reliable tickers ({len(reliable)}): {reliable['ticker'].tolist()}")
print(f"Unreliable tickers ({len(unreliable)}): {unreliable['ticker'].tolist()}")
print()
print(f"Real avg_spread_bps, computed from RELIABLE tickers only: "
      f"{reliable['median_spread_bps'].mean():.3f} bps")

reliable.to_csv("data/reliable_spread_tickers.csv", index=False)
summary.to_csv("data/spread_reliability_summary.csv", index=False)
print("\nSaved data/reliable_spread_tickers.csv and data/spread_reliability_summary.csv")