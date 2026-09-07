"""
evaluation/real_impact_calibration.py

Estimates the empirical impact-vs-size exponent from REAL classified
trades (Lee-Ready output), and compares it against the simulator's
calibration curve from impact_calibration.py.

Methodology:
  - Uses only quote_rule-classified trades (high confidence -- see
    batch_lee_ready.py's ground-truth validation: quote_rule trades were
    99.6% accurate against exchange-reported side; the tick_rule fallback
    was statistically indistinguishable from chance and is excluded here
    to avoid contaminating the analysis with likely-mislabeled trades).
  - "Impact" for a trade = signed distance between the trade price and
    the prevailing quote midpoint, in bps, sign-adjusted so a positive
    value always means "cost" (paid above mid on a buy, received below
    mid on a sell). This is the standard trade-level impact measure in
    the market microstructure literature and is exactly what the quote
    rule itself compares against.
  - "Participation" for a trade = trade size / that ticker's total
    traded volume on that calendar day (the standard Q/V_daily
    convention -- matches how Bouchaud's square-root law is usually
    stated, and how compute_impact() in the simulator is defined).

IMPORTANT LIMITATION: individual real trade prints are typically much
smaller relative to ADV than the participation range swept in
impact_calibration.py (0.5%-25%) -- large real-world orders get sliced
into many small child trades by execution algos, so a single tape print
rarely represents double-digit percent of a day's volume. This analysis
will likely only densely cover the LOW end of the participation range.
Report the actual coverage honestly rather than extrapolating beyond it.

Usage:
    python evaluation/real_impact_calibration.py --input data/tick/all_classified_merged.csv
"""

import argparse
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/tick/all_classified_merged.csv")
    parser.add_argument("--n-levels", type=int, default=15,
                         help="Number of log-spaced participation buckets")
    parser.add_argument("--min-per-bucket", type=int, default=30,
                         help="Drop buckets with fewer than this many trades")
    parser.add_argument("--output-dir", default="evaluation/plots")
    # Reference exponents from the simulator's impact_calibration.py run,
    # for direct comparison on the same plot. Update these if you rerun
    # that script and get different numbers.
    parser.add_argument("--sim-total-cost-exponent", type=float, default=0.136)
    parser.add_argument("--sim-isolated-impact-exponent", type=float, default=0.608)
    parser.add_argument("--sim-configured-exponent", type=float, default=0.6)
    parser.add_argument("--configured-eta-temporary", type=float, default=0.0005,
                         help="Current configs/default.yaml market.eta_temporary value, for comparison")
    parser.add_argument("--fit-min-participation", type=float, default=None,
                         help="Restrict the regression fit to buckets at or above this participation "
                              "rate (as a fraction, e.g. 0.0001 for 0.01%%). Use this to exclude the "
                              "floor-cost-dominated low end and/or noisy thin-sample high end from the "
                              "fit -- the full table is still printed regardless, this only affects "
                              "which rows feed the log-log regression.")
    parser.add_argument("--fit-max-participation", type=float, default=None,
                         help="Restrict the regression fit to buckets at or below this participation rate.")
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    print(f"Loaded {len(df)} total classified trades.")

    required = ["price", "midpoint", "trade_sign", "classification_method", "size", "symbol", "ts_event"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing required column(s): {missing}. "
                          f"Did this file come from lee_ready.py / batch_lee_ready.py?")

    # Parse trade date for daily volume normalization
    ts = pd.to_datetime(df["ts_event"], errors="coerce", utc=True)
    if ts.isna().all():
        ts = pd.to_datetime(df["ts_event"], unit="ns", errors="coerce", utc=True)
    df["trade_date"] = ts.dt.date

    if df["trade_date"].isna().all():
        raise SystemExit("Could not parse ts_event into dates -- check the timestamp format/column.")

    # Daily volume per ticker, computed from ALL trades (not just the
    # quote_rule-filtered subset used below), so participation is measured
    # against the true full day's volume, not an artificially shrunk one.
    daily_volume = df.groupby(["symbol", "trade_date"])["size"].transform("sum")
    df["daily_volume"] = daily_volume

    # Now filter to high-confidence trades only
    n_before = len(df)
    df = df[df["classification_method"] == "quote_rule"].copy()
    print(f"Filtered to {len(df)}/{n_before} quote_rule-classified trades "
          f"({len(df)/n_before:.1%}) for the impact analysis.")

    df = df[df["daily_volume"] > 0]
    df["participation"] = df["size"] / df["daily_volume"]

    # Signed cost relative to midpoint, sign-adjusted so positive = cost
    df["signed_cost_bps"] = df["trade_sign"] * (df["price"] - df["midpoint"]) / df["midpoint"] * 10_000
    df["abs_cost_bps"] = df["signed_cost_bps"].abs()

    # Report the actual participation range covered, since this is the
    # key honesty check on this analysis (see module docstring).
    p = df["participation"]
    print(f"\nParticipation rate range in real trade data: "
          f"min={p.min():.5%}, median={p.median():.5%}, "
          f"95th pct={p.quantile(0.95):.5%}, max={p.max():.5%}")
    print(f"(Simulator sweep covered 0.5% to 25% -- compare that range to the above "
          f"before treating this as a like-for-like comparison across the full range.)")

    # Log-spaced participation buckets. IMPORTANT: use integer bucket labels
    # and compute geometric midpoints from OUR OWN bin_edges array, rather
    # than reading back Interval.left/.right after the fact -- pd.cut with
    # include_lowest=True internally nudges the leftmost edge to make it
    # inclusive of the exact minimum, which can push it slightly negative
    # when the data spans many orders of magnitude (as real trade
    # participation typically does, unlike the simulator's controlled
    # sweep), breaking sqrt()/log() downstream.
    log_p = np.log10(p[p > 0])
    bin_edges = np.logspace(log_p.min(), log_p.max(), args.n_levels + 1)
    df["bucket_idx"] = pd.cut(df["participation"], bins=bin_edges,
                               include_lowest=True, labels=False)

    agg = df.groupby("bucket_idx", observed=True)["abs_cost_bps"].agg(["mean", "std", "count"])
    agg = agg[agg["count"] >= args.min_per_bucket]
    if len(agg) < 3:
        raise SystemExit(f"Only {len(agg)} buckets have >= {args.min_per_bucket} trades -- "
                          f"not enough to fit a reliable exponent. Try --min-per-bucket lower "
                          f"or --n-levels lower.")

    geo_mid_all = np.sqrt(bin_edges[:-1] * bin_edges[1:])
    bucket_geo_mid = geo_mid_all[agg.index.astype(int)]

    fit_mask = np.ones(len(agg), dtype=bool)
    if args.fit_min_participation is not None:
        fit_mask &= bucket_geo_mid >= args.fit_min_participation
    if args.fit_max_participation is not None:
        fit_mask &= bucket_geo_mid <= args.fit_max_participation
    if fit_mask.sum() < 2:
        raise SystemExit(f"Only {fit_mask.sum()} bucket(s) fall within "
                          f"[{args.fit_min_participation}, {args.fit_max_participation}] -- "
                          f"widen the range, at least 2 points are needed to fit a slope.")
    if not fit_mask.all():
        print(f"\nRestricting fit to {fit_mask.sum()}/{len(agg)} buckets within "
              f"[{args.fit_min_participation}, {args.fit_max_participation}] "
              f"(full table above still shows all buckets).")

    log_x = np.log(bucket_geo_mid[fit_mask])
    log_y = np.log(agg["mean"].values[fit_mask] + 1e-9)
    slope, intercept = np.polyfit(log_x, log_y, 1)

    print(f"\n=== Real-data impact calibration ===")
    print(agg.assign(participation_mid=bucket_geo_mid).round(4).to_string())
    print(f"\nEmpirical REAL-MARKET impact exponent (log-log slope): {slope:.3f}")
    print(f"Compare to:")
    print(f"  Simulator isolated impact component: {args.sim_isolated_impact_exponent:.3f}")
    print(f"  Simulator total realized cost:       {args.sim_total_cost_exponent:.3f}")
    print(f"  Simulator configured impact_exponent: {args.sim_configured_exponent:.3f}")
    print(f"  Bouchaud literature reference:        ~0.50")

    # ---- Back out an implied eta_temporary from the fitted intercept ----
    # compute_impact() in simulator/market.py: temp_impact_fraction =
    #   eta_temporary * participation**impact_exponent
    #   * (spread_bps/avg_spread_bps)**spread_impact_exp
    #   * (realised_vol)**vol_impact_exp
    # and temp_impact_bps = temp_impact_fraction * 10_000.
    #
    # In the fit region we selected, cost rises steeply with participation
    # (evidence impact dominates over the roughly-fixed spread floor there),
    # so approximating abs_cost_bps ~ eta_temporary * 10_000 * participation^slope
    # (dropping the spread/vol multiplicative terms, which should average
    # close to 1 across a large, diverse real sample under typical
    # conditions) lets us solve: eta_temporary ~ exp(intercept) / 10_000.
    #
    # This is an approximation, not an exact decomposition -- real data
    # alone can't cleanly separate spread-cost from impact-cost the way the
    # simulator's FillResult does internally. Treat this as a reasonable
    # first-pass recalibration, not a precise measurement.
    implied_eta_temporary = np.exp(intercept) / 10_000
    print(f"\n=== Implied eta_temporary from real data (approximation, see comments) ===")
    print(f"Implied eta_temporary: {implied_eta_temporary:.6f}")
    print(f"Configured eta_temporary: {args.configured_eta_temporary:.6f}")
    print(f"Ratio (implied / configured): {implied_eta_temporary/args.configured_eta_temporary:.2f}x")
    print(f"\nRECOMMENDED matched recalibration pair for configs/default.yaml market: section")
    print(f"  (use the fitted exponent and eta TOGETHER as a pair, not mixed with old defaults):")
    print(f"  impact_exponent: {slope:.4f}")
    print(f"  eta_temporary: {implied_eta_temporary:.6f}")

    # ---- Plot: real data vs simulator curves ----
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.loglog(bucket_geo_mid, agg["mean"], "o", color="#2E5EAA", label="Real market data (quote_rule trades)")
    fit_x = np.linspace(bucket_geo_mid[fit_mask].min(), bucket_geo_mid[fit_mask].max(), 100)
    fit_y = np.exp(intercept) * fit_x ** slope
    ax.loglog(fit_x, fit_y, "-", color="#2E5EAA", alpha=0.6,
              label=f"Real data fit (exp={slope:.2f})")

    # Overlay simulator's isolated-impact curve shape (normalized to
    # match at the pivot point of the real data's range, since absolute
    # levels aren't directly comparable -- shape/exponent is the point)
    fit_indices = np.where(fit_mask)[0]
    pivot_i = fit_indices[len(fit_indices) // 2]
    pivot_x = bucket_geo_mid[pivot_i]
    pivot_y = agg["mean"].iloc[pivot_i]
    sim_y = pivot_y * (fit_x / pivot_x) ** args.sim_isolated_impact_exponent
    ax.loglog(fit_x, sim_y, "--", color="#5CB85C",
              label=f"Simulator isolated impact shape (exp={args.sim_isolated_impact_exponent:.2f})")
    bouchaud_y = pivot_y * (fit_x / pivot_x) ** 0.5
    ax.loglog(fit_x, bouchaud_y, "--", color="#D9534F", label="Bouchaud sqrt-law (exp=0.50)")

    ax.set_xlabel("Participation rate: trade size / that day's total ticker volume (log)")
    ax.set_ylabel("Mean |cost vs midpoint| (bps, log)")
    ax.set_title("Real market impact vs simulator: functional form comparison\n"
                 "(shape comparison -- real data's participation range is much narrower "
                 "than the simulator sweep; see console output)", fontsize=10)
    ax.legend(fontsize=8)
    fig.tight_layout()

    os.makedirs(args.output_dir, exist_ok=True)
    out_path = f"{args.output_dir}/real_impact_calibration.png"
    fig.savefig(out_path, dpi=150)
    print(f"\nPlot saved to {out_path}")

    df.to_csv(f"{args.output_dir}/real_impact_calibration_raw.csv", index=False)
    print(f"Raw data saved to {args.output_dir}/real_impact_calibration_raw.csv")


if __name__ == "__main__":
    main()