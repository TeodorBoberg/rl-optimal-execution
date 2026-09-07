"""
check_folds.py

Pre-flight check on walk-forward fold datasets, run before committing ~8h
per fold to training. The previous fold-0 run cost a full training cycle to
discover a data problem (half trading days padded with zero-volume bars),
so this verifies the conditions that caused it.
"""

import glob
import os
import pandas as pd

files = sorted(glob.glob("data/walkforward/fold*.csv"))
if not files:
    raise SystemExit("No fold files found in data/walkforward/")

print(f"{'fold':>6} | {'rows':>10} | {'tickers':>7} | {'days/ticker':>11} | "
      f"{'bars/day':>10} | {'max zero-vol':>12} | {'min day vol':>12}")

ok = True
for f in files:
    name = os.path.basename(f).replace(".csv", "")
    df = pd.read_csv(f)
    g = df.groupby(["ticker", "day"])
    bars = sorted(g.size().unique())
    zero = g["volume"].apply(lambda s: (s == 0).mean()).max()
    dayvol = g["volume"].sum().min()
    days = df.groupby("ticker")["day"].nunique()

    bars_str = str(bars) if len(bars) <= 3 else f"{min(bars)}..{max(bars)}"
    print(f"{name:>6} | {len(df):>10,} | {df['ticker'].nunique():>7} | "
          f"{days.min():>5}-{days.max():<5} | {bars_str:>10} | "
          f"{zero:>11.2%} | {dayvol:>12,.0f}")

    if bars != [390]:
        print(f"         WARNING: not all days have exactly 390 bars")
        ok = False
    if zero > 0.10:
        print(f"         WARNING: a ticker-day has {zero:.1%} zero-volume bars "
              f"-- half day or data gap not filtered")
        ok = False

print("\nAll folds clean." if ok else "\nPROBLEMS FOUND -- do not train until resolved.")