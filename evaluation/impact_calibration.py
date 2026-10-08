"""
evaluation/impact_calibration.py

Validates the simulator's market impact model against the empirical
"square-root law" of market impact (Bouchaud et al.): temporary impact
cost scales roughly as (order size / average volume) ** 0.5.

This does NOT calibrate the absolute LEVEL of impact (the eta_temporary
coefficient / the "Y" constant in Bouchaud's formulation) -- that requires
real fill data, which per Anders' feedback isn't available yet (tick-level
trade classification, Lee-Ready rule, etc. -- a separate, larger project).

What this DOES validate: the FUNCTIONAL FORM. We sweep order size across
a realistic range of participation rates, execute against the actual
LOB-based MarketSimulator (not just algebraically evaluate compute_impact
in isolation -- that would trivially reproduce cfg.impact_exponent and
tell us nothing new), sampling many random (ticker, day, step) contexts so
realistic spread and volume variation (both drawn from real intraday data)
are folded in. Volatility REGIME is held at the baseline "calm" state
(the simulator only advances regime via .step(), which this script
deliberately skips) so the participation->cost relationship isn't
confounded by regime noise -- this gives a cleaner exponent estimate at
the cost of not capturing regime-conditional impact variation, which
would be a reasonable follow-up if useful.

We then fit a log-log regression of the SIMULATOR'S OWN REALIZED slippage
against participation rate and report the empirical exponent, alongside
the configured cfg.impact_exponent and the literature's ~0.5 reference.

Usage:
    python evaluation/impact_calibration.py --config configs/default.yaml
    python evaluation/impact_calibration.py --config configs/default.yaml --n-samples-per-level 200
"""

import argparse
import sys
import os
import dataclasses
from pathlib import Path
import yaml
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
os.chdir(_root)

from simulator.market import MarketSimulator, MarketConfig
from simulator.synthetic_data import load_csv_data
from simulator.data_split import train_test_split_days


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def build_market_cfg(cfg: dict) -> MarketConfig:
    m = cfg["market"]
    e = cfg["execution"]
    return MarketConfig(
        avg_daily_volume=m["avg_daily_volume"],
        steps_per_day=e["total_steps"],
        step_duration_min=e["step_duration_min"],
        avg_spread_bps=m["avg_spread_bps"],
        volatility_per_min=m["volatility_per_min"],
        eta_temporary=m["eta_temporary"],
        gamma_permanent=m["gamma_permanent"],
        impact_exponent=m.get("impact_exponent", 0.6),
        spread_impact_exp=m.get("spread_impact_exp", 0.3),
        vol_impact_exp=m.get("vol_impact_exp", 0.4),
        book_depth_levels=m["book_depth_levels"],
        book_replenish_halflife=m["book_replenish_halflife"],
        max_participation_rate=e["max_participation_rate"],
        adverse_selection_factor=m.get("adverse_selection_factor", 0.3),
        calm_vol=m.get("calm_vol", 0.0002),
        volatile_vol=m.get("volatile_vol", 0.0012),
        prob_calm_to_volatile=m.get("prob_calm_to_volatile", 0.005),
        prob_volatile_to_calm=m.get("prob_volatile_to_calm", 0.10),
        hawkes_baseline=m.get("hawkes_baseline", 10.0),
        hawkes_alpha=m.get("hawkes_alpha", 0.6),
        hawkes_decay=m.get("hawkes_decay", 0.3),
        news_spread_multiplier=m.get("news_spread_multiplier", 2.0),
        news_probability=m.get("news_probability", 0.005),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--n-levels", type=int, default=15,
                         help="Number of participation-rate levels to sweep")
    parser.add_argument("--n-samples-per-level", type=int, default=100,
                         help="Random (ticker, day, step) contexts sampled per level")
    parser.add_argument("--min-participation", type=float, default=0.005)
    parser.add_argument("--max-participation", type=float, default=None,
                         help="Defaults to cfg execution.max_participation_rate")
    parser.add_argument("--seed", type=int, default=99999)
    parser.add_argument("--output-dir", default="evaluation/plots")
    args = parser.parse_args()

    cfg = load_config(args.config)
    data_cfg = cfg["data"]
    exec_cfg = cfg["execution"]
    max_part = args.max_participation or exec_cfg["max_participation_rate"]

    if data_cfg["source"] != "csv":
        raise SystemExit("impact_calibration.py requires CSV data.")

    full_df = load_csv_data(data_cfg["path"], exec_cfg["step_duration_min"])
    test_frac = data_cfg.get("test_frac", 0.2)
    _, test_df = train_test_split_days(full_df, test_frac=test_frac)

    market_cfg = build_market_cfg(cfg)
    rng = np.random.default_rng(args.seed)

    # Pre-index available (day, step_idx) combos so we can sample realistic
    # spread/volume/regime contexts without re-deriving them each draw.
    days = sorted(test_df["day"].unique())
    total_steps = exec_cfg["total_steps"]

    participation_levels = np.logspace(
        np.log10(args.min_participation), np.log10(max_part), args.n_levels
    )

    records = []
    print(f"Sweeping {args.n_levels} participation levels "
          f"({args.min_participation:.1%} to {max_part:.1%}), "
          f"{args.n_samples_per_level} samples each...")

    for level in participation_levels:
        for _ in range(args.n_samples_per_level):
            day = int(rng.choice(days))
            day_data = test_df[test_df["day"] == day].reset_index(drop=True)
            if len(day_data) < 2:
                continue
            step_idx = int(rng.integers(0, min(len(day_data), total_steps) - 1))

            # IMPORTANT: replicate agent/env.py's reset() behavior, which
            # overrides sim.cfg.avg_daily_volume with the REAL per-ticker
            # ticker_adv (computed in synthetic_data.py's load_csv_data)
            # before every episode -- this script previously never did
            # that, so it always used the single flat config default
            # (market.avg_daily_volume) for every ticker regardless of
            # that ticker's real liquidity. For low-ADV names (ROKU, ETSY,
            # DUK) this made requested qty far exceed what their real
            # step volume could support, causing them to be capped almost
            # every time -- a measurement artifact, not a real finding.
            #
            # Uses dataclasses.replace() to build an explicit PER-SAMPLE
            # config copy, rather than mutating market_cfg in place --
            # MarketSimulator stores a direct reference to the cfg object
            # it's given (self.cfg = cfg, not a copy), so mutating a
            # shared config would silently leak one ticker's ADV into the
            # next sample if ticker_adv were ever missing for a row.
            if "ticker_adv" in day_data.columns and len(day_data) > 0:
                sample_cfg = dataclasses.replace(
                    market_cfg, avg_daily_volume=float(day_data["ticker_adv"].iloc[0])
                )
            else:
                sample_cfg = market_cfg

            sim = MarketSimulator(sample_cfg, rng=rng)
            sim.reset(day_data)
            sim.step_idx = step_idx
            sim._rebuild_lob()

            # IMPORTANT: compute_impact() in simulator/market.py defines its
            # own internal "participation" as qty / avg_vol_per_step (a
            # FIXED constant = avg_daily_volume / steps_per_day), NOT
            # qty / current_step_volume. This matches the literature's usual
            # convention (Bouchaud's law uses DAILY volume, not a single
            # bar's volume) but differs from participation_rate as reported
            # elsewhere in the pipeline (results.csv, the position cap, the
            # RL observation), which IS qty / current_step_volume. Sweeping
            # on the step-volume-relative definition here would bucket
            # together samples with very different TRUE model-internal
            # participation (since step_volume varies a lot across the
            # U-shaped intraday profile), attenuating the apparent exponent
            # toward zero via regression-to-the-mean. Sweep on the same
            # variable the model actually uses so the fit is meaningful.
            avg_vol_per_step = sample_cfg.avg_daily_volume / sample_cfg.steps_per_day
            qty = level * avg_vol_per_step
            step_volume = max(1, int(day_data.loc[step_idx, "volume"]))
            side = "buy" if rng.random() > 0.5 else "sell"

            fill = sim.execute(qty, side=side)
            if fill.filled_qty <= 0:
                continue

            records.append({
                "target_participation": level,  # = qty / avg_vol_per_step, matches compute_impact()
                "step_relative_participation": fill.participation_rate,  # qty / step_volume, for comparison only
                "abs_slippage_bps": abs(fill.slippage_bps),
                "temp_impact_bps": fill.temporary_impact_bps,
                "regime": fill.regime,
                "intended_qty": qty,
                "step_volume": step_volume,
                # execute() internally caps qty at step_volume * max_participation_rate
                # (using the CURRENT step's volume, not avg_vol_per_step) -- if that cap
                # bound, the actual executed size is smaller than intended, which would
                # corrupt exactly the high end of this sweep. Flag it so we can check.
                "was_capped": qty > step_volume * market_cfg.max_participation_rate,
            })

    df = pd.DataFrame(records)
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)
    df.to_csv(f"{output_dir}/impact_calibration_raw.csv", index=False)

    cap_rate = df["was_capped"].mean()
    print(f"\n{cap_rate:.1%} of samples had qty reduced by the step-volume position cap "
          f"(execute()'s internal max_qty = step_volume * max_participation_rate).")
    if cap_rate > 0.05:
        print("Excluding capped samples from the fit so high-participation levels aren't "
              "silently corrupted by clipped order sizes.")
        df = df[~df["was_capped"]]

    # Aggregate by target participation level (cleaner than realized, since
    # realized has execution noise from participation capping / partial fills)
    agg = df.groupby("target_participation")["abs_slippage_bps"].agg(["mean", "std", "count"])
    agg = agg[agg["count"] >= 5]  # drop levels with too few valid samples

    # Also fit the ISOLATED temp_impact_bps component (the multiplicative
    # markup from compute_impact() alone, excluding the spread-crossing cost
    # baked into the LOB's best-ask starting price). If total realized cost
    # shows a much flatter exponent than this isolated component, that's
    # evidence the flatness comes from a roughly-fixed spread-crossing floor
    # dominating at these order sizes -- not evidence the impact FORMULA
    # itself is broken.
    agg_impact_only = df.groupby("target_participation")["temp_impact_bps"].agg(["mean", "std", "count"])
    agg_impact_only = agg_impact_only[agg_impact_only["count"] >= 5]
    log_p_impact = np.log(agg_impact_only.index.values)
    log_impact = np.log(agg_impact_only["mean"].values + 1e-9)
    slope_impact_only, intercept_impact_only = np.polyfit(log_p_impact, log_impact, 1)

    log_p = np.log(agg.index.values)
    log_cost = np.log(agg["mean"].values + 1e-9)
    slope, intercept = np.polyfit(log_p, log_cost, 1)

    print("\n=== Impact calibration: participation level -> mean |slippage| bps ===")
    print(agg.round(3).to_string())

    print(f"\nEmpirical impact exponent (log-log slope of TOTAL realized slippage): {slope:.3f}")
    print(f"Empirical exponent of ISOLATED temp_impact_bps component only: {slope_impact_only:.3f}")
    print(f"Configured cfg.impact_exponent: {market_cfg.impact_exponent:.3f}")
    print("Bouchaud square-root law reference exponent: ~0.50 (commonly cited range: 0.4-0.7)")

    spread_dominance = (abs(slope_impact_only - market_cfg.impact_exponent) < 0.1
                        and slope < slope_impact_only - 0.15)
    if spread_dominance:
        print("\nInterpretation: the isolated impact component scales almost exactly as configured, "
              "but TOTAL realized cost is much flatter. This means the spread-crossing cost baked into "
              "the LOB's best-ask starting price (roughly fixed per fill, ~avg_spread_bps/2) is dominating "
              "total execution cost at the participation levels tested, not that the impact formula itself "
              "is miscalibrated. This is a real, defensible transaction-cost phenomenon: at small-to-moderate "
              "order sizes, spread cost dominates; the pure square-root impact law becomes the dominant driver "
              "mainly at larger sizes. Worth presenting both numbers, not just the total-cost exponent alone.")

    if spread_dominance:
        verdict = ("the isolated impact component matches the configured exponent, but total cost "
                   "is dominated by the roughly-fixed spread-crossing cost at these order sizes "
                   "(see interpretation above) -- not evidence the impact formula is miscalibrated")
    elif abs(slope - 0.5) < 0.15:
        verdict = "close to the canonical square-root law"
    elif abs(slope - market_cfg.impact_exponent) < 0.1:
        verdict = "consistent with the configured impact_exponent (as expected -- confirms internal consistency)"
    else:
        verdict = "notably different from both the configured exponent and the literature reference -- worth investigating"
    print(f"Verdict: simulator's realized impact scaling is {verdict}.")

    # ---- Plot: log-log realized cost vs participation, with fitted line
    #      and a normalized Bouchaud sqrt-law reference curve for shape
    #      comparison (NOT level calibration -- normalized to match the
    #      fitted curve at the median participation level, since we have
    #      no real fill data to calibrate the absolute Y constant).
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    ax = axes[0]
    ax.errorbar(agg.index, agg["mean"], yerr=agg["std"] / np.sqrt(agg["count"]),
                fmt="o", label="Simulator (realized, mean ± SE)", color="#2E5EAA")
    fit_x = np.linspace(agg.index.min(), agg.index.max(), 100)
    fit_y = np.exp(intercept) * fit_x ** slope
    ax.plot(fit_x, fit_y, "-", color="#2E5EAA", alpha=0.6,
            label=f"Fitted power law (exp={slope:.2f})")
    pivot_idx = len(agg) // 2
    pivot_p = agg.index[pivot_idx]
    pivot_cost = agg["mean"].iloc[pivot_idx]
    bouchaud_y = pivot_cost * (fit_x / pivot_p) ** 0.5
    ax.plot(fit_x, bouchaud_y, "--", color="#D9534F",
             label="Bouchaud sqrt-law (exp=0.50, shape only)")
    ax.set_xlabel("Participation rate (order size / avg per-step volume)")
    ax.set_ylabel("Mean |slippage| (bps)")
    ax.set_title("Impact vs participation (linear scale)")
    ax.legend(fontsize=8)

    ax2 = axes[1]
    ax2.loglog(agg.index, agg["mean"], "o", color="#2E5EAA", label="Simulator: total cost (realized)")
    ax2.loglog(fit_x, fit_y, "-", color="#2E5EAA", alpha=0.6, label=f"Fitted total cost (exp={slope:.2f})")
    ax2.loglog(agg_impact_only.index, agg_impact_only["mean"], "s", color="#5CB85C",
               label=f"Isolated impact component (exp={slope_impact_only:.2f})")
    ax2.loglog(fit_x, bouchaud_y, "--", color="#D9534F", label="Bouchaud sqrt-law (exp=0.50)")
    ax2.set_xlabel("Participation rate: qty/avg_vol_per_step (log)")
    ax2.set_ylabel("Mean |slippage| bps (log)")
    ax2.set_title("Log-log view (slope = impact exponent)")
    ax2.legend(fontsize=8)

    fig.suptitle("Impact model calibration: validating functional form against square-root law\n"
                 "(shape comparison only -- absolute level requires real fill data, not yet available)",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(f"{output_dir}/impact_calibration.png", dpi=150)
    print(f"\nPlot saved to {output_dir}/impact_calibration.png")
    print(f"Raw data saved to {output_dir}/impact_calibration_raw.csv")


if __name__ == "__main__":
    main()