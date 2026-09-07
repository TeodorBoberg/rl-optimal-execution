"""
simulator/data_split.py

Chronological, per-ticker train/test split for the intraday dataset.

Why chronological (not random): a random split lets the model train on a
day that falls *after* a day it's tested on, which is lookahead bias — the
model could pick up on regime/volatility patterns that a real deployment
would never have access to at decision time. Splitting on the calendar
axis (earliest days -> train, latest days -> test) is standard walk-forward
practice and is what a quant reviewer will expect to see.

Why per-ticker (not a single global cutoff): combined.csv lays tickers out
back-to-back (aapl: day 0-49, msft: day 50-99, ...), so a single global day
cutoff would just chop off whichever tickers happen to sit at the end of
the file — not a fair, representative holdout across the whole universe.
Splitting within each ticker's block means every ticker contributes to
both train and test.

IMPORTANT — day re-indexing:
Everything downstream (ExecutionEnv.reset()/get_day(), and
VecMarketSimulator's price/volume grid construction in
BulkVecEnv._load_data()) assumes the `day` column is a contiguous integer
range 0..n_days-1 that can be used as a direct row/array index. Splitting
by filtering rows breaks that contiguity (e.g. train could keep days
[0..39, 50..89, ...] with gaps). This module renumbers `day` to be
contiguous within each split, so nothing downstream needs to change.
"""

import numpy as np
import pandas as pd
from typing import Tuple


def train_test_split_days(
    df: pd.DataFrame,
    test_frac: float = 0.2,
    min_test_days: int = 1,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Chronologically split a day-indexed intraday DataFrame into train/test.

    If a 'ticker' column is present, the split is applied independently
    within each ticker's block of days (so every ticker appears in both
    train and test). If not (e.g. pure synthetic data with one continuous
    day range), the split is applied to the whole day range directly.

    Returns (train_df, test_df), each with 'day' renumbered to a
    contiguous 0..n-1 range.
    """
    if "ticker" in df.columns:
        groups = list(df.groupby("ticker", sort=False))
    else:
        groups = [(None, df)]

    train_frames, test_frames = [], []
    split_report = []

    for ticker, g in groups:
        days = np.sort(g["day"].unique())
        n = len(days)
        n_test = max(min_test_days, int(round(n * test_frac)))
        n_test = min(n_test, n - 1) if n > 1 else 0  # always keep >=1 train day

        train_days = days[: n - n_test]
        test_days = days[n - n_test:]

        train_frames.append(g[g["day"].isin(train_days)])
        test_frames.append(g[g["day"].isin(test_days)])
        split_report.append((ticker, n, len(train_days), len(test_days)))

    train_df = pd.concat(train_frames, ignore_index=True)
    test_df = pd.concat(test_frames, ignore_index=True)

    train_df = _renumber_days(train_df)
    test_df = _renumber_days(test_df)

    print("Train/test split (chronological, per-ticker):")
    for ticker, n, n_train, n_test in split_report:
        label = ticker if ticker is not None else "(all)"
        print(f"  {label:>8}: {n} days -> {n_train} train / {n_test} test")

    return train_df, test_df


def _renumber_days(df: pd.DataFrame) -> pd.DataFrame:
    """Remap 'day' to a contiguous 0..n-1 range, preserving chronological order."""
    df = df.copy()
    old_days = np.sort(df["day"].unique())
    remap = {old: new for new, old in enumerate(old_days)}
    df["day"] = df["day"].map(remap)
    return df