"""
filter_half_days.py

Removes half trading days (early closes) from the bar dataset.

US equity markets close at 1:00pm on ~3 days a year (July 3rd, the day
after Thanksgiving, Christmas Eve). tick_to_bars.py pads every session to a
full 390 one-minute bars, so on those days ~180 bars are appended with
volume = 0.

Why that breaks things: with zero volume the participation cap permits no
trading at all, so schedule-based benchmarks accumulate their entire
remaining inventory through the dead stretch, and force_fill then dumps it
into a zero-volume bar at the final step -- walking the synthetic depth
extension for hundreds of levels and producing costs in the hundreds of
thousands of bps. Observed on an NVDA day in walk-forward fold 0: cumulative
cost was 26 bps at step 388 and 533,989 bps after step 389.

Detection is by zero-volume fraction rather than by calendar date, so it
also catches genuine data gaps of the same shape.

Usage:
    python filter_half_days.py --input data/combined_1m_2yr_clipped.csv --output data/combined_1m_2yr_final.csv
"""

import argparse
import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/combined_1m_2yr_clipped.csv")
    parser.add_argument("--output", default="data/combined_1m_2yr_final.csv")
    parser.add_argument("--max-zero-frac", type=float, default=0.10,
                         help="Drop any ticker-day with more than this fraction of "
                              "zero-volume bars. 0.10 separates half days (~46%%) from "
                              "normal days (<5%%) at 1-MINUTE bars. At finer "
                              "granularity normal days have many more empty bars "
                              "(a thin name genuinely does not trade every 10s), so "
                              "this must be raised -- around 0.35 for 10-second bars. "
                              "Check the printed distribution before trusting it.")
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    print(f"Loaded {len(df):,} bars, {df.groupby(['ticker','day']).ngroups:,} ticker-days")

    zero_frac = df.groupby(["ticker", "day"])["volume"].apply(lambda s: (s == 0).mean())
    bad = zero_frac[zero_frac > args.max_zero_frac]

    print(f"\nDropping {len(bad)} ticker-day(s) with >{args.max_zero_frac:.0%} zero-volume bars")
    if len(bad):
        print(f"  zero-volume fraction among dropped: "
              f"{bad.min():.1%} to {bad.max():.1%}")
        print(f"  affected tickers: {sorted(bad.index.get_level_values(0).unique())}")
        per_ticker = bad.groupby(level=0).size()
        print(f"  days dropped per ticker: {per_ticker.to_dict()}")
        if per_ticker.nunique() == 1:
            print(f"  -> all tickers lost the same {per_ticker.iloc[0]} day(s), "
                  f"consistent with market-wide early closes rather than "
                  f"per-ticker data gaps")

    keep = set(bad.index)
    mask = ~pd.MultiIndex.from_arrays([df["ticker"], df["day"]]).isin(keep)
    out = df[mask].copy()

    # Renumber days contiguously per ticker; everything downstream assumes
    # a 0..n-1 range usable as a direct index.
    parts, offset = [], 0
    for tk, g in out.groupby("ticker", sort=False):
        g = g.copy()
        remap = {d: i + offset for i, d in enumerate(sorted(g["day"].unique()))}
        g["day"] = g["day"].map(remap)
        offset = g["day"].max() + 1
        parts.append(g)
    out = pd.concat(parts, ignore_index=True)

    print(f"\nRemaining: {len(out):,} bars, {out.groupby(['ticker','day']).ngroups:,} ticker-days")
    print(out.groupby("ticker")["day"].nunique().to_string())

    zf = out.groupby(["ticker", "day"])["volume"].apply(lambda s: (s == 0).mean())
    print(f"\nMax zero-volume fraction remaining: {zf.max():.2%}")

    out.to_csv(args.output, index=False)
    print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()