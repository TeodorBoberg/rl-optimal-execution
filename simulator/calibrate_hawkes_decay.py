"""
simulator/calibrate_hawkes_decay.py

Measures the real decay rate of "excess trading activity" (deviation from
the expected intraday volume profile) from real 1-minute bar data, to
calibrate hawkes_decay -- the ONE Hawkes parameter that has a clean,
legitimate real-data analog in this simulator's design (see conversation
context: HawkesOrderFlow is a self-referential per-step EWMA driven by the
SIMULATED order's own size, not a classical point process fit to
independent real order arrivals -- hawkes_alpha/hawkes_baseline don't have
as direct a real-data mapping, but the DECAY RATE of real activity
clustering does).

Methodology:
  1. Remove the deterministic intraday U-shape (using the already-extracted
     real_volume_profile.csv) from each ticker-day's volume series, leaving
     a residual "excess activity" series per ticker-day.
  2. Compute the pooled autocorrelation of these residuals at lags 1..60
     minutes, using only within-day pairs (never crossing a day boundary,
     which would create spurious autocorrelation from the overnight reset).
  3. Fit an exponential decay ACF(lag) = A * exp(-decay_rate * lag) via
     nonlinear least squares.
  4. hawkes_decay is applied once per simulator step (self.intensity decays
     by exp(-hawkes_decay) per .step() call) -- since we're calibrating on
     1-minute bars and the simulator now also steps once per minute, the
     units line up directly: hawkes_decay ~= decay_rate from this fit.

Usage:
    python simulator/calibrate_hawkes_decay.py --input data/combined_1m_clean.csv
"""

import argparse
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit


def compute_residuals(df: pd.DataFrame, profile: pd.Series) -> dict:
    """Returns {(ticker, day): residual_array} for every ticker-day."""
    residuals = {}
    for (ticker, day), g in df.groupby(["ticker", "day"]):
        g = g.sort_values("step")
        if len(g) != len(profile):
            continue  # skip incomplete days
        day_total = g["volume"].sum()
        if day_total <= 0:
            continue
        volume_frac = g["volume"].values / day_total
        expected_frac = profile.values
        # Log-ratio residual: robust to the multiplicative/lognormal-ish
        # nature of volume data, and symmetric around 0.
        residual = np.log((volume_frac + 1e-9) / (expected_frac + 1e-9))
        # Demean WITHIN the ticker-day. Without this, a day where the ticker
        # traded heavily all session (earnings, index rebalance, macro event)
        # has positive residuals at EVERY step, so residuals correlate at all
        # lags for reasons unrelated to intraday order-flow clustering. That
        # day-level component inflates long-lag ACF and biases the fitted
        # decay rate downward -- verified on synthetic data: with realistic
        # day-to-day activity variation the fit recovered 0.0149 against a
        # true injected decay of 0.030, while demeaned data recovered 0.0289.
        # Negligible on a short sample; dominant over multi-year data
        # spanning many volatility regimes.
        residual = residual - residual.mean()
        residuals[(ticker, day)] = residual
    return residuals


def pooled_autocorrelation(residuals: dict, max_lag: int) -> np.ndarray:
    """
    Pooled ACF across many independent within-day residual series.
    For each lag, pools all valid (t, t+lag) pairs across ALL ticker-days
    into one array and computes a single Pearson correlation -- more
    statistically stable than averaging per-day correlations separately,
    especially for days with limited data.
    """
    acf = np.zeros(max_lag)
    for lag in range(1, max_lag + 1):
        xs, ys = [], []
        for arr in residuals.values():
            if len(arr) <= lag:
                continue
            xs.append(arr[:-lag])
            ys.append(arr[lag:])
        if not xs:
            acf[lag - 1] = np.nan
            continue
        x = np.concatenate(xs)
        y = np.concatenate(ys)
        acf[lag - 1] = np.corrcoef(x, y)[0, 1]
    return acf


def exp_decay(lag, amplitude, decay_rate):
    return amplitude * np.exp(-decay_rate * lag)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/combined_1m_clean.csv")
    parser.add_argument("--profile", default="simulator/real_volume_profile.csv")
    parser.add_argument("--max-lag", type=int, default=60,
                         help="Max lag (in minutes) to compute autocorrelation over")
    parser.add_argument("--fit-max-lag", type=int, default=30,
                         help="Restrict the exponential fit to lags <= this, "
                              "since ACF estimates get noisier at long lags "
                              "(fewer independent within-day pairs)")
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    profile_df = pd.read_csv(args.profile)
    profile = profile_df.set_index("step")["volume_fraction"]

    print(f"Computing residuals for {df.groupby(['ticker','day']).ngroups} ticker-days...")
    residuals = compute_residuals(df, profile)
    print(f"  {len(residuals)} complete ticker-days used.")

    print(f"\nComputing pooled autocorrelation, lags 1-{args.max_lag} minutes...")
    acf = pooled_autocorrelation(residuals, args.max_lag)

    print("\n=== Autocorrelation of excess trading activity by lag (minutes) ===")
    for lag in [1, 2, 3, 5, 10, 15, 20, 30, 45, 60]:
        if lag <= args.max_lag:
            print(f"  lag={lag:3d} min: ACF={acf[lag-1]:.4f}")

    # Fit exponential decay to the early, less-noisy part of the ACF
    fit_lags = np.arange(1, min(args.fit_max_lag, args.max_lag) + 1)
    fit_acf = acf[:len(fit_lags)]
    valid = ~np.isnan(fit_acf)

    try:
        popt, _ = curve_fit(exp_decay, fit_lags[valid], fit_acf[valid],
                             p0=[0.3, 0.1], bounds=([0, 0], [2, 5]))
        amplitude, decay_rate = popt
        print(f"\n=== Fitted exponential decay ===")
        print(f"ACF(lag) ~= {amplitude:.4f} * exp(-{decay_rate:.4f} * lag)")
        print(f"\nFitted decay_rate: {decay_rate:.4f} (per minute)")
        print(f"Currently configured hawkes_decay: 0.3")
        print(f"Ratio (real / configured): {decay_rate/0.3:.2f}x")
        print(f"\nHalf-life of excess activity clustering: {np.log(2)/decay_rate:.1f} minutes")
        print(f"(i.e. a burst of above-average trading activity takes about "
              f"{np.log(2)/decay_rate:.1f} minutes for its predictive effect "
              f"on future activity to fall by half)")
    except RuntimeError as e:
        print(f"\nFit failed to converge: {e}")
        print("Check the printed ACF values above -- if they're very noisy or "
              "don't show a clear decay pattern, the exponential decay "
              "assumption itself may not fit well.")


if __name__ == "__main__":
    main()