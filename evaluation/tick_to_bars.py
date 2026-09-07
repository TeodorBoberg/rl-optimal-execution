"""
evaluation/tick_to_bars.py

Aggregates raw Databento tbbo tick files into higher-frequency OHLCV bars
(default: 1-minute), matching combine.py's exact output conventions so
the result drops directly into configs/default.yaml's data.path with no
other pipeline changes needed:
  - Per-ticker price normalization: all price columns (open/high/low/
    close/bid/ask/vwap) divided by that ticker's first close * 100, same
    as combine.py. Safe because everything downstream is bps/ratio-based;
    this just keeps price SCALE consistent with the rest of the pipeline.
  - Global day offsetting: each ticker's trading days get a contiguous,
    globally-unique 'day' index (ticker A: 0..48, ticker B: 49..97, ...),
    same convention as combine.py.

Only regular trading hours (9:30-16:00 ET) are included -- tick pulls
typically include pre/post-market prints, which would corrupt bar
continuity and break the existing 6.5hr trading day assumption.

Empty bars (a minute with zero trades -- more likely on thinner names)
are forward-filled from the prior bar's close, with volume=0, rather than
left as gaps -- every trading day ends up with a complete, well-formed
step sequence.

Usage:
    python evaluation/tick_to_bars.py --input-dir data/tick --bar-minutes 1
    python evaluation/tick_to_bars.py --input-dir data/tick --bar-minutes 1 --output data/combined_1m.csv
"""

import argparse
import glob
import os
import numpy as np
import pandas as pd


def load_tick_file(path: str) -> pd.DataFrame:
    """
    Load ONE tick file, reading only the columns actually needed for bar
    construction. The tbbo schema has 19 columns; we need 5. With multi-GB
    files (a single quarter of NVDA ticks is ~880MB on disk), reading all
    columns and concatenating every file for a ticker at once -- which the
    previous version did -- needs 10-20GB of RAM and will OOM. Reading
    per-file with usecols keeps peak memory around 1GB.
    """
    needed = ["ts_event", "price", "size", "bid_px_00", "ask_px_00"]
    # 'sequence' is only used for dedup; include it when present.
    header = pd.read_csv(path, nrows=0)
    usecols = [c for c in needed + ["sequence"] if c in header.columns]
    missing = [c for c in needed if c not in header.columns]
    if missing:
        raise ValueError(f"{path} missing required column(s): {missing}")

    df = pd.read_csv(path, usecols=usecols)

    ts = pd.to_datetime(df["ts_event"], errors="coerce", utc=True)
    if ts.isna().all():
        ts = pd.to_datetime(df["ts_event"], unit="ns", errors="coerce", utc=True)
    df["ts_event"] = ts
    df = df.dropna(subset=["ts_event"])

    dedup_cols = [c for c in ["ts_event", "sequence", "price", "size"] if c in df.columns]
    df = df.drop_duplicates(subset=dedup_cols)

    df = df.sort_values("ts_event").reset_index(drop=True)
    df["ts_event_eastern"] = df["ts_event"].dt.tz_convert("US/Eastern")
    return df


def build_bars_for_ticker(df: pd.DataFrame, bar_seconds: int) -> pd.DataFrame:
    """Aggregate one ticker's tick data into OHLCV bars, regular trading hours only."""
    eastern = df["ts_event_eastern"]
    df = df[(eastern.dt.time >= pd.Timestamp("09:30").time()) &
            (eastern.dt.time < pd.Timestamp("16:00").time())].copy()
    if df.empty:
        return pd.DataFrame()

    df["trade_date"] = df["ts_event_eastern"].dt.date
    df["bar_bucket"] = df["ts_event_eastern"].dt.floor(f"{bar_seconds}s")

    bars = []
    for trade_date, day_df in df.groupby("trade_date"):
        session_start = pd.Timestamp.combine(trade_date, pd.Timestamp("09:30").time())
        session_start = session_start.tz_localize("US/Eastern")
        # 6.5hr regular session = 23,400 seconds. Sub-minute bars are
        # supported so decision frequency can be varied independently of
        # the data pipeline.
        n_bars = int(23_400 / bar_seconds)
        expected_buckets = pd.date_range(session_start, periods=n_bars,
                                          freq=f"{bar_seconds}s")

        # Compute per-tick mid and spread_bps FIRST, then take medians of
        # those (not median(bid) and median(ask) independently). This
        # guarantees a non-negative spread by construction: bid/ask for
        # the bar are DERIVED from the median mid and median spread, so
        # ask >= bid always holds, even if the bucket contains some noisy
        # or genuinely crossed individual ticks (real data has some --
        # e.g. ETSY had 20 crossed raw ticks out of 384,921). Taking
        # median(bid) and median(ask) as two SEPARATE independent
        # statistics could, in principle, produce median(ask) < median(bid)
        # for a given bucket -- this caused a real crash during training:
        # compute_impact() raises the spread ratio to a fractional power,
        # and Python's ** on a negative base with a non-integer exponent
        # returns a COMPLEX number rather than raising an error, which
        # then blew up float() deep into a 5M-timestep run.
        day_df = day_df.copy()
        day_df["_mid"] = (day_df["bid_px_00"] + day_df["ask_px_00"]) / 2
        day_df["_spread_bps"] = (day_df["ask_px_00"] - day_df["bid_px_00"]) / day_df["_mid"] * 10_000

        grouped = day_df.groupby("bar_bucket")
        ohlc = grouped["price"].agg(["first", "max", "min", "last"])
        ohlc.columns = ["open", "high", "low", "close"]
        vol = grouped["size"].sum().rename("volume")
        vwap = (grouped.apply(lambda g: (g["price"] * g["size"]).sum() / g["size"].sum())
                .rename("vwap"))

        median_mid = grouped["_mid"].median()
        # Small positive floor as a second line of defense -- belt and
        # braces on top of the by-construction guarantee above.
        median_spread_bps = grouped["_spread_bps"].median().clip(lower=0.01)
        half_spread_price = median_mid * median_spread_bps / 20_000
        bid = (median_mid - half_spread_price).rename("bid")
        ask = (median_mid + half_spread_price).rename("ask")
        spread_bps_col = median_spread_bps.rename("spread_bps")

        bar_df = pd.concat([ohlc, vol, vwap, bid, ask, spread_bps_col], axis=1)
        bar_df = bar_df.reindex(expected_buckets)

        # Forward-fill genuinely empty minutes (no trades that minute)
        bar_df[["open", "high", "low", "close", "vwap", "bid", "ask", "spread_bps"]] = (
            bar_df[["open", "high", "low", "close", "vwap", "bid", "ask", "spread_bps"]].ffill()
        )
        bar_df["volume"] = bar_df["volume"].fillna(0)
        # If the very first bar(s) of the day had no trades, back-fill from
        # the first bar that DID trade (can't forward-fill something with
        # no prior value)
        bar_df[["open", "high", "low", "close", "vwap", "bid", "ask", "spread_bps"]] = (
            bar_df[["open", "high", "low", "close", "vwap", "bid", "ask", "spread_bps"]].bfill()
        )

        bar_df["trade_date"] = trade_date
        bar_df["step"] = range(len(bar_df))
        bar_df["timestamp"] = bar_df.index
        bars.append(bar_df.reset_index(drop=True))

    result = pd.concat(bars, ignore_index=True)
    # NOTE: spread_bps is already computed correctly (and safely -- see
    # comments above) per-bar during aggregation. Do NOT recompute it here
    # from bid/ask -- that's exactly the calculation that caused a real
    # crash (median(bid) and median(ask) computed independently could, in
    # rare cases, produce ask < bid for a given bucket).
    #
    # Day numbering deliberately does NOT happen here. This function now
    # processes ONE FILE at a time (each file is a distinct date range), so
    # numbering here would restart at 0 for every chunk. The caller assigns
    # day numbers once, chronologically, after all of a ticker's files are
    # combined.
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="data/tick")
    parser.add_argument("--pattern", default="*_tbbo_*.csv")
    parser.add_argument("--bar-seconds", type=int, default=60,
                         help="Bar length in seconds. 60 = 1-minute (390 bars/day), "
                              "10 = 10-second (2,340 bars/day). Must divide 23,400 "
                              "evenly.")
    parser.add_argument("--output", default="data/combined_1m.csv")
    parser.add_argument("--exclude-dates", default="",
                         help="Comma-separated YYYY-MM-DD dates to drop entirely, e.g. days "
                              "Databento flagged as degraded quality.")
    args = parser.parse_args()

    if 23_400 % args.bar_seconds != 0:
        raise SystemExit(f"--bar-seconds must divide 23,400 (a 6.5hr session) "
                          f"evenly; {args.bar_seconds} does not.")

    exclude_dates = set()
    if args.exclude_dates.strip():
        exclude_dates = {pd.Timestamp(d.strip()).date()
                          for d in args.exclude_dates.split(",") if d.strip()}
        print(f"Excluding {len(exclude_dates)} flagged date(s): {sorted(exclude_dates)}")

    all_files = sorted(glob.glob(os.path.join(args.input_dir, args.pattern)))
    # Stale Lee-Ready output files are named "..._tbbo_..._classified.csv" and
    # therefore MATCH the tbbo glob. Including them would double-count ticks.
    all_files = [f for f in all_files if "_classified" not in os.path.basename(f)]
    if not all_files:
        raise SystemExit(f"No files matching {args.pattern} in {args.input_dir}")

    # Group files by ticker symbol (handles multiple pulls per ticker)
    by_ticker = {}
    for f in all_files:
        symbol = os.path.basename(f).split("_tbbo_")[0].upper()
        by_ticker.setdefault(symbol, []).append(f)

    print(f"Found {len(by_ticker)} tickers, {len(all_files)} files total: "
          f"{sorted(by_ticker.keys())}")

    all_ticker_bars = []
    day_offset = 0

    for symbol in sorted(by_ticker.keys()):
        files = sorted(by_ticker[symbol])
        print(f"\nProcessing {symbol} ({len(files)} file(s))...")

        # Process ONE FILE AT A TIME and keep only the resulting BARS.
        # Bars are ~390 rows/day, so accumulated bars stay small (a few MB
        # per ticker) even when the underlying tick files total several GB.
        # Bars never span file boundaries because each file is a distinct
        # date range, so this is exact -- not an approximation.
        per_file_bars = []
        total_ticks = 0
        for path in files:
            ticks = load_tick_file(path)
            total_ticks += len(ticks)
            if exclude_dates:
                keep = ~ticks["ts_event_eastern"].dt.date.isin(exclude_dates)
                ticks = ticks[keep]
            file_bars = build_bars_for_ticker(ticks, args.bar_seconds)
            del ticks  # release the large frame before reading the next file
            if not file_bars.empty:
                per_file_bars.append(file_bars)
            print(f"    {os.path.basename(path)}: "
                  f"{0 if file_bars.empty else file_bars['trade_date'].nunique()} trading days")

        if not per_file_bars:
            print(f"  WARNING: no regular-hours data for {symbol}, skipping.")
            continue

        bars = pd.concat(per_file_bars, ignore_index=True)
        # Overlapping pulls can produce the same trade_date from two files;
        # keep one bar per (trade_date, step).
        bars = bars.drop_duplicates(subset=["trade_date", "step"], keep="first")
        bars = bars.sort_values(["trade_date", "step"]).reset_index(drop=True)

        # Assign day numbers ONCE, chronologically, across the whole ticker.
        unique_dates = sorted(bars["trade_date"].unique())
        date_to_day = {d: i for i, d in enumerate(unique_dates)}
        bars["day"] = bars["trade_date"].map(date_to_day)

        # combine.py's price normalization: all price columns / first close * 100
        first_close = bars["close"].iloc[0]
        for col in ["open", "high", "low", "close", "bid", "ask", "vwap"]:
            bars[col] = bars[col] / first_close * 100.0

        bars["day"] += day_offset
        day_offset = bars["day"].max() + 1
        bars["ticker"] = symbol.lower()

        n_days = bars["day"].nunique()
        n_bars_per_day = int(23_400 / args.bar_seconds)
        print(f"  {total_ticks:,} ticks -> {n_days} trading days x {n_bars_per_day} "
              f"bars/day = {len(bars):,} total bars")

        all_ticker_bars.append(bars)

    combined = pd.concat(all_ticker_bars, ignore_index=True)
    combined = combined[["timestamp", "day", "step", "open", "high", "low", "close",
                          "volume", "spread_bps", "bid", "ask", "vwap", "ticker"]]

    combined.to_csv(args.output, index=False)
    print(f"\nCombined {len(by_ticker)} tickers, {combined['day'].nunique()} total days, "
          f"{len(combined)} total bars.")
    print(f"Saved to {args.output}")
    print(f"\nTo use: update configs/default.yaml -> data.path: \"{args.output}\"")
    print(f"And update configs/default.yaml -> execution.total_steps: {int(23_400/args.bar_seconds)} "
          f"(currently likely 78 for 5-min bars)")


if __name__ == "__main__":
    main()