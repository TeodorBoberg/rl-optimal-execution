"""
filter_half_days_by_date.py

Removes half trading days by DATE rather than by zero-volume threshold.

Why: at 1-minute bars, half days (1pm early closes) are unmistakable --
~46% zero-volume bars against <5% for normal days, two clean clusters. At
10-second bars that separation disappears: the distribution is smooth
(median 9.9%, 95th pct 37.9%, no gap), because a thin name genuinely does
not trade in every 10-second window. Any threshold then cuts through the
middle of a continuum and removes ordinary low-liquidity days. Observed
with --max-zero-frac 0.35 on 10s data: PG lost 143 of 488 days, CVX 112,
JPM 109 -- precisely the three lowest-volume tickers, while the liquid
names lost only the ~5 real early closes.

Half days are a property of the calendar, not of the bar size. This
identifies them once at 1-minute granularity, where detection is
unambiguous, then applies the same date list at any granularity.

Usage:
    python filter_half_days_by_date.py \
        --reference data/combined_1m_2yr_clipped.csv \
        --input data/combined_10s_clipped.csv \
        --output data/combined_10s_final.csv
"""

import argparse
import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", default="data/combined_1m_2yr_clipped.csv",
                         help="1-minute file, used only to identify half-day DATES.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--ref-zero-frac", type=float, default=0.30,
                         help="Zero-volume threshold applied to the REFERENCE "
                              "1-minute file. Half days sit near 46%% there and "
                              "normal days under 5%%, so anything in 0.15-0.40 "
                              "gives the same answer.")
    args = parser.parse_args()

    ref = pd.read_csv(args.reference, usecols=["ticker", "day", "volume", "timestamp"])
    # utc=True is required: timestamps span a DST boundary, so the column
    # contains mixed UTC offsets (EST and EDT) and pandas refuses to parse
    # them into one series without a common timezone. Converting to
    # US/Eastern afterwards recovers the correct local trading date.
    ref["date"] = (pd.to_datetime(ref["timestamp"], errors="coerce", utc=True)
                     .dt.tz_convert("US/Eastern").dt.date)
    zf = ref.groupby(["ticker", "day"])["volume"].apply(lambda s: (s == 0).mean())
    bad = zf[zf > args.ref_zero_frac]

    dates = (ref.set_index(["ticker", "day"]).loc[bad.index, "date"]
                .dropna().unique())
    dates = sorted(pd.to_datetime(pd.Series(list(dates))).dt.date.unique())

    print(f"Reference: {args.reference}")
    print(f"Half-day ticker-days above {args.ref_zero_frac:.0%} zero volume: {len(bad)}")
    print(f"Distinct half-day DATES identified: {len(dates)}")
    sub = ref.set_index(["ticker", "day"]).loc[bad.index].reset_index()
    counts = sub.groupby("date")["ticker"].nunique()
    for d, n in counts.items():
        print(f"    {d}: {n} ticker(s)")
    if len(counts) and counts.nunique() == 1:
        print(f"  -> every affected date hits all {counts.iloc[0]} tickers, "
              f"consistent with market-wide early closes")

    df = pd.read_csv(args.input)
    if "timestamp" not in df.columns:
        raise SystemExit("Input has no timestamp column; cannot match by date.")
    df["date"] = (pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
                    .dt.tz_convert("US/Eastern").dt.date)

    before_days = df.groupby("ticker")["day"].nunique()
    keep = ~df["date"].isin(set(dates))
    out = df[keep].drop(columns=["date"]).copy()

    parts, offset = [], 0
    for tk, g in out.groupby("ticker", sort=False):
        g = g.copy()
        remap = {d: i + offset for i, d in enumerate(sorted(g["day"].unique()))}
        g["day"] = g["day"].map(remap)
        offset = g["day"].max() + 1
        parts.append(g)
    out = pd.concat(parts, ignore_index=True)

    after_days = out.groupby("ticker")["day"].nunique()
    print(f"\n{'ticker':>8} | {'before':>6} | {'after':>6} | {'dropped':>7}")
    for tk in sorted(after_days.index):
        print(f"{tk:>8} | {before_days[tk]:>6} | {after_days[tk]:>6} | "
              f"{before_days[tk]-after_days[tk]:>7}")

    dropped = (before_days - after_days)
    if dropped.nunique() == 1:
        print(f"\nAll tickers lost the same {dropped.iloc[0]} day(s) -- correct: "
              f"half days are market-wide.")
    else:
        print(f"\nWARNING: tickers lost different numbers of days "
              f"({dropped.min()}-{dropped.max()}). Half days should affect every "
              f"ticker equally; investigate before using this output.")

    zf_out = out.groupby(["ticker", "day"])["volume"].apply(lambda s: (s == 0).mean())
    print(f"\nRemaining zero-volume fraction: median {zf_out.median():.1%}, "
          f"max {zf_out.max():.1%}")
    print("(A high max is expected and fine at fine granularity -- it reflects "
          "genuinely thin days, not half days.)")

    out.to_csv(args.output, index=False)
    print(f"\nSaved {len(out):,} rows to {args.output}")


if __name__ == "__main__":
    main()