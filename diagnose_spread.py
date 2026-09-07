import pandas as pd
import numpy as np
import glob
import os

# Check a "bad" ticker (ETSY) and a "good" one (AAPL) directly at the raw
# tick level, before any bar aggregation, to isolate where the problem is.
for symbol in ["etsy", "aapl"]:
    files = glob.glob(f"data/tick/{symbol}_tbbo_*.csv")
    if not files:
        print(f"No files found for {symbol}")
        continue
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    print(f"\n{'='*60}\n{symbol.upper()}: {len(df)} raw ticks\n{'='*60}")

    print("publisher_id distribution:")
    print(df["publisher_id"].value_counts().to_string())

    raw_spread_bps = (df["ask_px_00"] - df["bid_px_00"]) / ((df["ask_px_00"] + df["bid_px_00"]) / 2) * 10_000
    print(f"\nRaw tick-level spread_bps stats:")
    print(raw_spread_bps.describe(percentiles=[0.01, 0.1, 0.5, 0.9, 0.99]))

    print(f"\nRows with bid_px_00 <= 0: {(df['bid_px_00'] <= 0).sum()}")
    print(f"Rows with ask_px_00 <= 0: {(df['ask_px_00'] <= 0).sum()}")
    print(f"Rows with crossed quote (bid > ask): {(df['bid_px_00'] > df['ask_px_00']).sum()}")
    print(f"Rows with raw spread_bps > 100: {(raw_spread_bps > 100).sum()} "
          f"({(raw_spread_bps > 100).mean():.2%})")

    # If multiple publishers exist, check spread by publisher separately --
    # mixing venues could itself cause this
    if df["publisher_id"].nunique() > 1:
        print("\nSpread by publisher_id:")
        df["raw_spread_bps"] = raw_spread_bps
        print(df.groupby("publisher_id")["raw_spread_bps"].agg(["mean", "median", "count"]).to_string())