"""
simulator/synthetic_data.py

Generates realistic synthetic intraday OHLCV data with:
  - Geometric Brownian Motion price dynamics
  - U-shaped intraday volume profile (high at open/close)
  - Realistic bid/ask spread dynamics
  - Hawkes-process-inspired volume clustering
"""

import os
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional


@dataclass
class SyntheticMarketConfig:
    n_days: int = 252
    steps_per_day: int = 78          # 78 x 5-min bars = 6.5hr trading day
    initial_price: float = 100.0
    avg_daily_volume: int = 5_000_000
    volatility_per_min: float = 0.0003
    avg_spread_bps: float = 5.0
    step_duration_min: int = 5
    seed: Optional[int] = 42


def u_shaped_volume_profile(n_steps: int) -> np.ndarray:
    """
    Generates a U-shaped intraday volume distribution.
    Empirically, ~10% of daily volume trades in the first and last 30 min,
    with a midday trough around 4-5% per 30-min period.
    """
    t = np.linspace(0, 1, n_steps)
    # U-shape: high at 0 and 1, low in the middle
    profile = 0.5 + 2.5 * (t - 0.5) ** 2
    # Add a morning spike (first ~10% of day)
    profile[:max(1, n_steps // 10)] *= 1.4
    profile = profile / profile.sum()  # normalize to sum to 1
    return profile


def load_empirical_volume_profile(
    path: str = "simulator/real_volume_profile.csv",
    n_steps: Optional[int] = None,
) -> np.ndarray:
    """
    Load a real, empirically-measured intraday volume profile (see
    simulator/calibrate_microstructure.py), as a more realistic
    replacement for the assumed u_shaped_volume_profile() formula.

    Used by the VWAP benchmark strategy's trade schedule, so the
    benchmark itself trades against real measured intraday liquidity
    patterns rather than a hand-tuned formula -- this also makes the
    RL-vs-VWAP comparison fairer, since VWAP is now scheduling against
    reality rather than an assumption.

    Falls back to u_shaped_volume_profile() if the file doesn't exist,
    so this is safe to call in synthetic-only setups without erroring.
    If the saved profile's length doesn't match n_steps (e.g. it was
    computed at a different bar granularity), linearly resamples it to
    match rather than silently misaligning the schedule.
    """
    if not os.path.exists(path):
        if n_steps is None:
            raise ValueError("n_steps is required when falling back to the synthetic profile "
                              f"(real profile not found at {path})")
        return u_shaped_volume_profile(n_steps)

    df = pd.read_csv(path)
    profile = df["volume_fraction"].values.astype(float)

    if n_steps is not None and len(profile) != n_steps:
        old_x = np.linspace(0, 1, len(profile))
        new_x = np.linspace(0, 1, n_steps)
        profile = np.interp(new_x, old_x, profile)

    profile = profile / profile.sum()
    return profile


def generate_intraday_data(
    cfg: SyntheticMarketConfig,
) -> pd.DataFrame:
    """
    Returns a DataFrame with shape (n_days * steps_per_day, columns).
    Columns: [day, step, timestamp, open, high, low, close, volume,
              spread_bps, bid, ask, vwap]
    """
    rng = np.random.default_rng(cfg.seed)

    vol_per_step = cfg.volatility_per_min * np.sqrt(cfg.step_duration_min)
    volume_profile = u_shaped_volume_profile(cfg.steps_per_day)

    records = []
    price = cfg.initial_price

    for day in range(cfg.n_days):
        # Overnight gap (small drift between days)
        price *= np.exp(rng.normal(0, vol_per_step * 2))

        day_open = price
        day_volume = rng.integers(
            int(cfg.avg_daily_volume * 0.6),
            int(cfg.avg_daily_volume * 1.4)
        )

        for step in range(cfg.steps_per_day):
            # Price process: GBM with slight mean reversion intraday
            drift = -0.005 * (price / day_open - 1)  # mild mean reversion
            ret = drift + rng.normal(0, vol_per_step)
            open_price = price
            close_price = price * np.exp(ret)

            # Intrabar high/low
            intrabar_vol = abs(ret) * rng.uniform(1.0, 2.5)
            high_price = max(open_price, close_price) * np.exp(intrabar_vol * 0.5)
            low_price = min(open_price, close_price) * np.exp(-intrabar_vol * 0.5)

            # Volume: follow profile + Hawkes-like clustering
            base_vol = day_volume * volume_profile[step]
            hawkes_multiplier = rng.lognormal(0, 0.3)  # vol-of-vol
            step_volume = int(base_vol * hawkes_multiplier)

            # Spread: widens when volatility is high, narrows at high volume
            realized_vol = abs(ret) / vol_per_step  # relative to expected
            spread_bps = cfg.avg_spread_bps * max(0.5, realized_vol)

            mid = (open_price + close_price) / 2
            half_spread = mid * spread_bps / 20_000  # bps / 2 / 10000
            bid = mid - half_spread
            ask = mid + half_spread

            # VWAP approximation for the step
            vwap = (open_price + high_price + low_price + close_price) / 4

            records.append({
                "day": day,
                "step": step,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": step_volume,
                "spread_bps": spread_bps,
                "bid": bid,
                "ask": ask,
                "vwap": vwap,
            })
            price = close_price

    df = pd.DataFrame(records)
    df["ticker_adv"] = cfg.avg_daily_volume
    return df


def load_csv_data(path: str, step_duration_min: int = 5) -> pd.DataFrame:
    """
    Load real OHLCV data from a CSV.
    Expected columns: [timestamp, open, high, low, close, volume]

    If the file already has correct `day` (and optionally `ticker`) columns
    — e.g. produced by combine.py for a multi-ticker dataset — those are
    respected as-is. This matters because multiple tickers can share the
    exact same calendar dates/timestamps; re-deriving `day` from `date`
    alone (grouping only by calendar date) would silently merge different
    tickers' same-day bars into one scrambled "trading day", splicing
    unrelated price series together step by step.
    """
    df = pd.read_csv(path, parse_dates=["timestamp"])

    if "day" in df.columns:
        # Respect existing day assignment (e.g. from combine.py). Sort within
        # each day to guarantee correct step order without touching day ids.
        sort_cols = (["ticker", "day", "timestamp"] if "ticker" in df.columns
                     else ["day", "timestamp"])
        df = df.sort_values(sort_cols).reset_index(drop=True)
        if "step" not in df.columns:
            df["step"] = df.groupby("day").cumcount()
    else:
        # Single-ticker file with no day info yet — safe to infer from date,
        # since there's only one ticker's worth of timestamps in this file.
        df = df.sort_values("timestamp").reset_index(drop=True)
        df["date"] = df["timestamp"].dt.date
        df["day"] = df.groupby("date").ngroup()
        df["step"] = df.groupby("day").cumcount()

    # Add spread estimate if not in data (Kyle's lambda approximation)
    if "spread_bps" not in df.columns:
        typical_price = df["close"]
        df["spread_bps"] = 5.0  # fallback: 5bps flat
    if "bid" not in df.columns:
        half = df["close"] * df["spread_bps"] / 20_000
        df["bid"] = df["close"] - half
        df["ask"] = df["close"] + half
    if "vwap" not in df.columns:
        df["vwap"] = (df["open"] + df["high"] + df["low"] + df["close"]) / 4

    # Per-ticker average daily volume, computed from the actual data — used
    # by the simulator to scale Hawkes intensity updates correctly for each
    # ticker's real liquidity. Without this, a single global config constant
    # (market.avg_daily_volume) gets applied to every ticker regardless of
    # how liquid it actually is, understating relative order-flow intensity
    # for thin names and overstating it for very liquid ones.
    if "ticker" in df.columns:
        daily_vol = df.groupby(["ticker", "day"])["volume"].sum()
        ticker_adv = daily_vol.groupby("ticker").transform("mean")
        adv_lookup = ticker_adv.rename("ticker_adv").reset_index()
        df = df.merge(adv_lookup, on=["ticker", "day"], how="left")
    else:
        daily_vol = df.groupby("day")["volume"].sum()
        df["ticker_adv"] = daily_vol.mean()

    return df


def get_day(df: pd.DataFrame, day: int) -> pd.DataFrame:
    """Extract one trading day's data."""
    return df[df["day"] == day].reset_index(drop=True)