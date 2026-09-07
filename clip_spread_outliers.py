"""
clip_spread_outliers.py

Clips implausible spread_bps values in an existing bar file, and rebuilds
bid/ask consistently from the clipped spread.

Why: EQUS.MINI is a partial-venue composite (not full NBBO). When the venue
holding the best quote drops out momentarily, the composite BBO goes
absurdly wide. On the 2-year dataset this produces 554 bars with spread
>1000bps -- 299 of them AAPL, the most liquid name in the universe, which
does not have 10% spreads. These are data artifacts, not market events.

They matter because spread_bps sets the simulated order book's width: a
1000bps bar means any execution there pays ~500bps just crossing the
spread, which then shows up as tail execution cost that isn't real.

Clipping is applied PER TICKER as a multiple of that ticker's own median,
so it adapts to genuinely wider-spread names rather than imposing one
absolute ceiling across a universe spanning SPY (0.34bps) to JPM (5.6bps).

Usage:
    python clip_spread_outliers.py --input data/combined_1m_2yr.csv --output data/combined_1m_2yr_clipped.csv
"""

import argparse
import pandas as pd
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/combined_1m_2yr.csv")
    parser.add_argument("--output", default="data/combined_1m_2yr_clipped.csv")
    parser.add_argument("--max-multiple", type=float, default=20.0,
                         help="Clip spread_bps at this multiple of the ticker's own median.")
    parser.add_argument("--absolute-ceiling", type=float, default=100.0,
                         help="Additional hard ceiling in bps, applied after the per-ticker rule.")
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    print(f"Loaded {len(df):,} bars, {df['ticker'].nunique()} tickers")

    medians = df.groupby("ticker")["spread_bps"].median()
    print("\nPer-ticker median spread and resulting clip ceiling:")
    n_clipped_total = 0
    for ticker, med in medians.sort_values().items():
        ceiling = min(med * args.max_multiple, args.absolute_ceiling)
        mask = (df["ticker"] == ticker) & (df["spread_bps"] > ceiling)
        n = int(mask.sum())
        n_clipped_total += n
        print(f"  {ticker:6s}: median={med:7.3f}  ceiling={ceiling:7.3f}  "
              f"clipped={n:6d} ({n/max((df['ticker']==ticker).sum(),1):.3%})")
        df.loc[mask, "spread_bps"] = ceiling

    print(f"\nTotal bars clipped: {n_clipped_total:,} ({n_clipped_total/len(df):.4%})")

    # Rebuild bid/ask from the (possibly clipped) spread so they stay
    # consistent with spread_bps. mid is preserved exactly.
    mid = (df["bid"] + df["ask"]) / 2.0
    half = mid * df["spread_bps"] / 20_000.0
    df["bid"] = mid - half
    df["ask"] = mid + half

    assert (df["spread_bps"] >= 0).all(), "negative spread after clipping"
    assert (df["ask"] >= df["bid"]).all(), "crossed quote after rebuild"

    print("\nSpread stats after clipping:")
    print(df.groupby("ticker")["spread_bps"].agg(["mean", "median", "std", "max"]).round(3).to_string())

    df.to_csv(args.output, index=False)
    print(f"\nSaved to {args.output}")
    print(f"Update configs/default.yaml -> data.path: \"{args.output}\"")

    eq_weight = df.groupby("ticker")["spread_bps"].median().mean()
    print(f"\nEqual-weight-per-ticker average of medians: {eq_weight:.3f} bps "
          f"(use this for market.avg_spread_bps)")


if __name__ == "__main__":
    main()