"""
evaluation/calibrate_book_dynamics.py

Measures two simulator parameters directly from tick data:

    spread_widening_factor   2.0   how much the spread widens after a trade
                                   consumes liquidity
    book_replenish_halflife  5     how fast top-of-book size recovers, in
                                   simulator steps

Unlike the impact-factor exponents, these are single-dimension quantities
measured over the range the data actually covers, so they do not require
extrapolating from tape-print sizes to institutional order sizes.

SPREAD WIDENING
    For each classified trade, compare the prevailing spread just before
    against the spread shortly after, bucketed by trade size relative to
    displayed top-of-book size. The simulator applies
    spread_widening_factor when a trade consumes a level, so the relevant
    comparison is trades that consume most or all of the displayed size.

BOOK REPLENISHMENT
    After a trade consumes displayed size on one side, track how that
    side's displayed size recovers over subsequent quote updates. Fit
        size(t) = size_inf - (size_inf - size_0) * exp(-t / tau)
    and convert tau to a half-life in simulator steps.

    Note tbbo carries only TOP OF BOOK (bid_px_00/bid_sz_00), so this
    measures level-1 replenishment. Deeper book behaviour would need
    MBP-10, which is why book_depth_levels remains unmeasurable.

Usage:
    python evaluation/calibrate_book_dynamics.py --max-files 26
"""

import sys
import os
import glob
import argparse
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
os.chdir(_root)

import numpy as np
import pandas as pd

from evaluation.lee_ready import classify_trades


REQ = ["ts_event", "price", "size", "bid_px_00", "ask_px_00", "bid_sz_00", "ask_sz_00"]


def load(path, max_trades):
    header = pd.read_csv(path, nrows=0)
    missing = [c for c in REQ if c not in header.columns]
    if missing:
        return None
    df = pd.read_csv(path, usecols=REQ)
    ts = pd.to_datetime(df["ts_event"], errors="coerce", utc=True)
    if ts.isna().all():
        ts = pd.to_datetime(df["ts_event"], unit="ns", errors="coerce", utc=True)
    df["ts_event"] = ts
    df = df.dropna(subset=["ts_event"]).sort_values("ts_event").reset_index(drop=True)
    eastern = df["ts_event"].dt.tz_convert("US/Eastern")
    df = df[(eastern.dt.time >= pd.Timestamp("09:30").time()) &
            (eastern.dt.time < pd.Timestamp("16:00").time())].copy()
    if df.empty:
        return None
    df["trade_date"] = df["ts_event"].dt.tz_convert("US/Eastern").dt.date
    if max_trades and len(df) > max_trades:
        df = df.iloc[:max_trades].copy()
    cl = classify_trades(df, price_col="price", bid_col="bid_px_00",
                          ask_col="ask_px_00", ts_col="ts_event")
    return cl[cl["classification_method"] == "quote_rule"].copy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="data/tick")
    parser.add_argument("--pattern", default="*_tbbo_*.csv")
    parser.add_argument("--max-files", type=int, default=26)
    parser.add_argument("--max-trades-per-file", type=int, default=500000)
    parser.add_argument("--lookahead", type=int, default=60,
                         help="Ticks ahead to track recovery over.")
    parser.add_argument("--step-seconds", type=int, default=60,
                         help="Simulator step length, for converting the fitted "
                              "time constant into steps. 1-minute bars = 60.")
    args = parser.parse_args()

    files = sorted(glob.glob(os.path.join(args.input_dir, args.pattern)))
    files = [f for f in files if "_classified" not in os.path.basename(f)]
    by_ticker = {}
    for f in files:
        by_ticker.setdefault(os.path.basename(f).split("_tbbo_")[0], []).append(f)
    picked = []
    if args.max_files == 0:
        picked = files
    else:
        per = max(1, args.max_files // len(by_ticker))
        for tk in sorted(by_ticker):
            picked.extend(sorted(by_ticker[tk])[:per])

    print(f"Processing {len(picked)} file(s) across {len(by_ticker)} ticker(s)\n")

    widen_rows, recov_rows = [], []
    for path in picked:
        cl = load(path, args.max_trades_per_file)
        if cl is None or len(cl) < 1000:
            print(f"  {os.path.basename(path)}: skipped")
            continue

        cl = cl.reset_index(drop=True)
        mid = cl["midpoint"].values
        spread = (cl["ask_px_00"].values - cl["bid_px_00"].values) / mid * 1e4
        sign = cl["trade_sign"].values
        sz = cl["size"].values
        bid_sz = cl["bid_sz_00"].values
        ask_sz = cl["ask_sz_00"].values
        t = cl["ts_event"].values.astype("datetime64[s]").astype(np.int64)

        # Displayed size on the side being hit: buys lift the ask.
        disp = np.where(sign > 0, ask_sz, bid_sz).astype(float)
        ok = (disp > 0) & np.isfinite(spread) & (spread > 0)
        consume = np.where(ok, sz / np.maximum(disp, 1e-9), np.nan)

        n = len(cl)
        nxt = np.arange(n) + 1
        valid = ok & (nxt < n)
        i = np.where(valid)[0]
        if len(i):
            widen_rows.append(pd.DataFrame({
                "consume_ratio": consume[i],
                "spread_before": spread[i],
                "spread_after": spread[i + 1],
            }))

        # Replenishment: trades that consumed at least 80% of displayed size.
        big = np.where(ok & (consume >= 0.8) & (np.arange(n) + args.lookahead < n))[0]
        if len(big) > 20000:
            big = big[np.linspace(0, len(big) - 1, 20000).astype(int)]
        for k in big:
            side_sz = ask_sz if sign[k] > 0 else bid_sz
            base = side_sz[k]
            if base <= 0:
                continue
            seg = side_sz[k + 1: k + 1 + args.lookahead].astype(float)
            dt = t[k + 1: k + 1 + args.lookahead] - t[k]
            m = dt >= 0
            if m.sum() < 5:
                continue
            recov_rows.append(pd.DataFrame({
                "dt_sec": dt[m],
                "size_ratio": seg[m] / base,
            }))
        print(f"  {os.path.basename(path)}: {len(cl):,} trades, "
              f"{len(big):,} full-consumption events")

    # ---- Spread widening ----
    print("\n" + "=" * 62)
    print("SPREAD WIDENING")
    print("=" * 62)
    if widen_rows:
        w = pd.concat(widen_rows, ignore_index=True)
        w = w[np.isfinite(w).all(axis=1) & (w["spread_before"] > 0)]
        w["ratio"] = w["spread_after"] / w["spread_before"]
        bins = [0, 0.25, 0.5, 0.8, 1.0, 2.0, 5.0, np.inf]
        w["bucket"] = pd.cut(w["consume_ratio"], bins=bins)
        agg = w.groupby("bucket", observed=True)["ratio"].agg(["mean", "median", "count"])
        print("\nSpread after / spread before, by fraction of displayed size consumed:")
        print(agg.round(4).to_string())
        full = w[w["consume_ratio"] >= 0.8]["ratio"]
        if len(full) > 100:
            print(f"\n  Trades consuming >=80% of displayed size: "
                  f"mean ratio {full.mean():.4f}, median {full.median():.4f}, "
                  f"n={len(full):,}")
            print(f"  configured spread_widening_factor: 2.0")
    else:
        print("No usable observations.")

    # ---- Replenishment ----
    print("\n" + "=" * 62)
    print("TOP-OF-BOOK REPLENISHMENT")
    print("=" * 62)
    if recov_rows:
        r = pd.concat(recov_rows, ignore_index=True)
        r = r[np.isfinite(r).all(axis=1) & (r["dt_sec"] >= 0)]
        prof = r.groupby("dt_sec")["size_ratio"].agg(["mean", "count"])
        prof = prof[prof["count"] >= 100].head(120)
        print("\nDisplayed size relative to pre-trade, by seconds elapsed:")
        show = prof.loc[prof.index.isin([0, 1, 2, 3, 5, 10, 15, 30, 45, 60])]
        print(show.round(4).to_string())

        y = prof["mean"].values
        x = prof.index.values.astype(float)
        if len(x) >= 8:
            inf = float(np.median(y[-max(3, len(y)//5):]))
            y0 = float(y[0])
            gap = inf - y0
            if abs(gap) > 1e-6:
                z = (inf - y) / gap
                m = (z > 1e-6) & (z <= 1.5) & (x > 0)
                if m.sum() >= 5:
                    tau = -1.0 / np.polyfit(x[m], np.log(z[m]), 1)[0]
                    half_sec = tau * np.log(2)
                    print(f"\n  size_0={y0:.3f}, size_inf={inf:.3f}")
                    print(f"  fitted tau = {tau:.1f} s, half-life = {half_sec:.1f} s")
                    print(f"  in simulator steps ({args.step_seconds}s each): "
                          f"{half_sec/args.step_seconds:.3f}")
                    print(f"  configured book_replenish_halflife: 5 steps "
                          f"({5*args.step_seconds} s)")
                else:
                    print("\n  Could not fit a decay -- recovery is not exponential.")
            else:
                print("\n  No measurable recovery gap.")
    else:
        print("No usable observations.")


if __name__ == "__main__":
    main()