"""
evaluation/measure_permanent_impact.py

Measures REAL permanent market impact from tick data, to validate (or
refute) the simulator's `gamma_permanent` -- the one major cost parameter
whose shape AND level have never been checked against data.

Method
------
For each classified trade at time t with size q:
  1. record the prevailing mid price at t (pre-trade)
  2. record the mid price at t + H for several horizons H (5, 15, 60 min)
  3. signed impact = trade_sign * (mid(t+H) - mid(t)) / mid(t) * 10_000 bps
  4. bucket by participation (q / that day's total volume) and fit
     impact ~ gamma * participation^exponent in log-log space

Signing by trade direction is what separates permanent impact from ordinary
price drift: unsigned, forward returns average to roughly zero. If
buyer-initiated trades are systematically followed by higher prices and
seller-initiated by lower, that residual is permanent impact.

Only quote_rule-classified trades are used. The tick-rule fallback was
measured at 51.2% accuracy (95% CI [49.9%, 52.5%]) against exchange-reported
side -- indistinguishable from chance -- so including it would inject
sign noise directly into the quantity being measured.

The simulator models permanent impact as LINEAR in participation
(gamma_permanent * participation, Kyle-style). A fitted exponent near 1.0
supports that; materially below 1.0 indicates it is concave like temporary
impact, and the linear form is wrong.

Sampling
--------
Processes a subset of tick files by default. A few million trades is ample
for this estimate and keeps runtime to minutes rather than an hour over the
full ~18GB. Use --max-files 0 for everything.

Usage:
    python evaluation/measure_permanent_impact.py
    python evaluation/measure_permanent_impact.py --max-files 12 --horizons 5,15,60
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
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from evaluation.lee_ready import classify_trades


def process_file(path, horizons_min, max_trades_per_file):
    """Return per-trade signed forward impact at each horizon, for one file."""
    needed = ["ts_event", "price", "size", "bid_px_00", "ask_px_00"]
    header = pd.read_csv(path, nrows=0)
    missing = [c for c in needed if c not in header.columns]
    if missing:
        return None
    usecols = [c for c in needed + ["side"] if c in header.columns]
    df = pd.read_csv(path, usecols=usecols)

    ts = pd.to_datetime(df["ts_event"], errors="coerce", utc=True)
    if ts.isna().all():
        ts = pd.to_datetime(df["ts_event"], unit="ns", errors="coerce", utc=True)
    df["ts_event"] = ts
    df = df.dropna(subset=["ts_event"]).sort_values("ts_event").reset_index(drop=True)

    # Regular trading hours only
    eastern = df["ts_event"].dt.tz_convert("US/Eastern")
    df = df[(eastern.dt.time >= pd.Timestamp("09:30").time()) &
            (eastern.dt.time < pd.Timestamp("16:00").time())].copy()
    if df.empty:
        return None
    df["trade_date"] = df["ts_event"].dt.tz_convert("US/Eastern").dt.date

    if max_trades_per_file and len(df) > max_trades_per_file:
        df = df.iloc[:max_trades_per_file].copy()

    classified = classify_trades(df, price_col="price", bid_col="bid_px_00",
                                  ask_col="ask_px_00", ts_col="ts_event")
    classified = classified[classified["classification_method"] == "quote_rule"].copy()
    if classified.empty:
        return None

    # Daily volume for participation normalisation
    daily_vol = classified.groupby("trade_date")["size"].transform("sum")
    classified["participation"] = classified["size"] / daily_vol.replace(0, np.nan)

    out = []
    for date, g in classified.groupby("trade_date"):
        g = g.sort_values("ts_event").reset_index(drop=True)
        mid = g["midpoint"].values
        t = g["ts_event"].values.astype("datetime64[s]").astype(np.int64)
        for H in horizons_min:
            # Index of the first trade at least H minutes later
            fwd_idx = np.searchsorted(t, t + H * 60, side="left")
            valid = fwd_idx < len(g)
            if not valid.any():
                continue
            idx = np.where(valid)[0]
            fwd_mid = mid[fwd_idx[idx]]
            ret_bps = (fwd_mid - mid[idx]) / mid[idx] * 10_000

            # Demean WITHIN the day before signing. Permanent impact is a
            # tiny signal (a single trade is typically ~0.002% of daily
            # volume) sitting on top of ordinary price movement with a
            # standard deviation orders of magnitude larger. Signing alone
            # cancels common drift only if buys and sells are exactly
            # balanced; any imbalance leaks that day's drift straight into
            # the estimate. Removing the day's mean forward return first
            # makes the measure robust to that imbalance.
            ret_bps = ret_bps - ret_bps.mean()

            signed = g["trade_sign"].values[idx] * ret_bps
            out.append(pd.DataFrame({
                "horizon_min": H,
                "participation": g["participation"].values[idx],
                "signed_impact_bps": signed,
                "unsigned_return_bps": ret_bps,
            }))
    if not out:
        return None
    return pd.concat(out, ignore_index=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="data/tick")
    parser.add_argument("--pattern", default="*_tbbo_*.csv")
    parser.add_argument("--max-files", type=int, default=13,
                         help="Number of tick files to process (0 = all).")
    parser.add_argument("--max-trades-per-file", type=int, default=400000)
    parser.add_argument("--horizons", default="5,15,60",
                         help="Forward horizons in minutes.")
    parser.add_argument("--configured-gamma", type=float, default=0.00005)
    parser.add_argument("--output-dir", default="evaluation/plots")
    args = parser.parse_args()

    horizons = [int(h) for h in args.horizons.split(",")]
    files = sorted(glob.glob(os.path.join(args.input_dir, args.pattern)))
    files = [f for f in files if "_classified" not in os.path.basename(f)]
    if not files:
        raise SystemExit(f"No files matching {args.pattern} in {args.input_dir}")

    # Spread across tickers rather than taking the first N files (which
    # would all be the same ticker and give a single-name estimate).
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
        picked = picked[:args.max_files] if args.max_files < len(picked) else picked

    print(f"Processing {len(picked)} file(s) across {len(by_ticker)} ticker(s), "
          f"up to {args.max_trades_per_file:,} trades each\n")

    frames = []
    for f in picked:
        res = process_file(f, horizons, args.max_trades_per_file)
        n = 0 if res is None else len(res)
        print(f"  {os.path.basename(f)}: {n:,} trade-horizon observations")
        if res is not None:
            frames.append(res)

    if not frames:
        raise SystemExit("No usable observations.")
    data = pd.concat(frames, ignore_index=True)
    data = data[np.isfinite(data["participation"]) & np.isfinite(data["signed_impact_bps"])]
    print(f"\nTotal: {len(data):,} observations")

    os.makedirs(args.output_dir, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 6))

    print("\n" + "=" * 74)
    print("PERMANENT IMPACT BY HORIZON")
    print("=" * 74)
    for H in horizons:
        d = data[data["horizon_min"] == H]
        if len(d) < 100:
            print(f"\nHorizon {H} min: too few observations ({len(d)})")
            continue

        p = d["participation"]
        bins = np.logspace(np.log10(max(p.min(), 1e-9)), np.log10(p.max()), 13)
        d = d.assign(bucket=pd.cut(d["participation"], bins=bins,
                                    include_lowest=True, labels=False))
        agg = d.groupby("bucket")["signed_impact_bps"].agg(["mean", "std", "count"])
        agg = agg[agg["count"] >= 50]
        if len(agg) < 3:
            print(f"\nHorizon {H} min: too few populated buckets")
            continue

        # Standard error and t-stat per bucket. Permanent impact per trade is
        # a very small signal against large price noise, so without these it
        # is easy to fit an exponent to what is actually noise.
        agg["se"] = agg["std"] / np.sqrt(agg["count"])
        agg["t_stat"] = agg["mean"] / agg["se"].replace(0, np.nan)

        geo = np.sqrt(bins[:-1] * bins[1:])[agg.index.astype(int)]
        agg = agg.assign(participation_mid=geo)

        print(f"\n--- Horizon {H} min ---")
        print(agg[["participation_mid", "mean", "se", "t_stat", "count"]].round(4).to_string())

        n_sig = int((agg["t_stat"].abs() > 2).sum())
        print(f"  {n_sig}/{len(agg)} buckets have |t| > 2 "
              f"(i.e. distinguishable from zero)")

        unsigned_mean = d["unsigned_return_bps"].mean()
        signed_mean = d["signed_impact_bps"].mean()
        signed_se = d["signed_impact_bps"].std() / np.sqrt(len(d))
        print(f"  mean UNSIGNED forward return: {unsigned_mean:+.4f} bps "
              f"(~0 by construction after within-day demeaning)")
        print(f"  mean SIGNED impact:           {signed_mean:+.4f} bps "
              f"+/- {signed_se:.4f} (t={signed_mean/max(signed_se,1e-12):.1f}, n={len(d):,})")

        sig = agg[(agg["mean"] > 0) & (agg["t_stat"] > 2)]
        if len(sig) >= 3:
            slope, intercept = np.polyfit(np.log(sig["participation_mid"]),
                                           np.log(sig["mean"]), 1)
            print(f"  fitted exponent: {slope:.3f}  "
                  f"(simulator assumes LINEAR, i.e. exponent = 1.0)")
            print(f"  implied impact at participation=1%: "
                  f"{np.exp(intercept) * (0.01 ** slope):.4f} bps")
        else:
            print(f"  NOT fitting an exponent: only {len(sig)} bucket(s) are both "
                  f"positive and statistically distinguishable from zero. "
                  f"Fitting here would be fitting noise.")

        ax.loglog(agg["participation_mid"], agg["mean"].clip(lower=1e-4),
                  "o-", label=f"{H} min horizon")

    ref_x = np.logspace(-6, -2, 50)
    ax.loglog(ref_x, ref_x * 1e4 * args.configured_gamma, "--", color="grey",
              label=f"simulator linear (gamma={args.configured_gamma})")
    ax.set_xlabel("Participation (trade size / daily volume)")
    ax.set_ylabel("Signed permanent impact (bps)")
    ax.set_title("Real permanent impact vs participation, by forward horizon")
    ax.legend(fontsize=8)
    fig.tight_layout()
    out_png = f"{args.output_dir}/permanent_impact.png"
    fig.savefig(out_png, dpi=150)

    data.to_csv(f"{args.output_dir}/permanent_impact_raw.csv", index=False)
    print(f"\nPlot saved to {out_png}")
    print(f"Raw observations saved to {args.output_dir}/permanent_impact_raw.csv")
    print("\nReading this: impact should GROW with horizon if it is genuinely")
    print("permanent (it persists), and flatten once it stabilises. Impact that")
    print("DECAYS toward zero at longer horizons was temporary, not permanent.")


if __name__ == "__main__":
    main()