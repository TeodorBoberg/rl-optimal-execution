"""
simulator/calibrate_microstructure.py

Extracts real market microstructure statistics from combined_1m.csv to
replace two of the simulator's currently-assumed defaults:

  1. avg_spread_bps -- currently a single flat config guess (5.0 bps for
     all 19 tickers). Real spread varies a lot across the universe (a
     mega-cap like AAPL trades much tighter than a thinner name like
     ROKU) -- this computes the real universe-wide average AND a
     per-ticker breakdown for reference/disclosure.

  2. The intraday volume profile -- currently u_shaped_volume_profile()
     in synthetic_data.py is a hand-tuned FORMULA (not measured), used
     both by the simulator's Hawkes intensity scaling and by the VWAP
     benchmark strategy's trade schedule. This computes the REAL average
     per-minute volume fraction across the whole universe and saves it
     as a reusable array, to replace the assumed formula.

Usage:
    python simulator/calibrate_microstructure.py --input data/combined_1m.csv
"""

import argparse
import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/combined_1m.csv")
    parser.add_argument("--output-profile", default="simulator/real_volume_profile.csv")
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    required = ["spread_bps", "volume", "step", "ticker", "day"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing required column(s): {missing}")

    # ---- 1. Real spread ----
    print("=== Real average spread (bps) ===")
    per_ticker_spread = df.groupby("ticker")["spread_bps"].agg(["mean", "median", "std"])
    print(per_ticker_spread.round(3).to_string())

    universe_avg_spread = df["spread_bps"].mean()
    universe_median_spread = df["spread_bps"].median()
    print(f"\nUniverse-wide mean spread: {universe_avg_spread:.3f} bps")
    print(f"Universe-wide median spread: {universe_median_spread:.3f} bps")
    print(f"Currently configured (market.avg_spread_bps): 5.0 bps")
    print(f"Ratio (real mean / configured): {universe_avg_spread/5.0:.2f}x")

    # ---- 2. Real intraday volume profile ----
    print("\n=== Real intraday volume profile ===")
    # Normalize each ticker-day to sum to 1 first, so high/low-ADV names
    # contribute equally to the SHAPE (not weighted by their absolute size)
    df["day_key"] = df["ticker"] + "_" + df["day"].astype(str)
    day_totals = df.groupby("day_key")["volume"].transform("sum")
    df["volume_frac"] = df["volume"] / day_totals.replace(0, np.nan)

    profile = df.groupby("step")["volume_frac"].mean()
    profile = profile.fillna(profile.mean())  # guard against any all-zero days
    profile = profile / profile.sum()  # renormalize to sum to exactly 1

    n_steps = len(profile)
    print(f"Profile computed over {n_steps} steps "
          f"(should match execution.total_steps in your config).")
    print(f"\nProfile shape check -- fraction of volume in each sixth of the day:")
    sixth = n_steps // 6
    for i in range(6):
        start, end = i * sixth, min((i + 1) * sixth, n_steps)
        frac = profile.iloc[start:end].sum()
        print(f"  Steps {start}-{end}: {frac:.1%}")

    profile_df = pd.DataFrame({"step": profile.index, "volume_fraction": profile.values})
    profile_df.to_csv(args.output_profile, index=False)
    print(f"\nReal volume profile saved to {args.output_profile}")
    print(f"(Compare this to the assumed u_shaped_volume_profile() formula in "
          f"synthetic_data.py -- next step is wiring this real profile in as a "
          f"replacement, both for the VWAP benchmark's schedule and the "
          f"simulator's Hawkes intensity scaling.)")


if __name__ == "__main__":
    main()