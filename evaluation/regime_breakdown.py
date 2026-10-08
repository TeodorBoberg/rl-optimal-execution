"""
evaluation/regime_breakdown.py

Splits the result by market condition rather than reporting one average.

Currently every figure is a single number across all episodes. That hides
whether the edge comes from calm markets or turbulent ones, from liquid
tickers or thin ones, from buys or sells. A practitioner will ask, and
"it averages to 28%" is a weaker answer than knowing where it comes from.

Uses evaluation/results.csv, so it needs no training and no simulation --
just a backtest that has already been run.

Usage:
    python evaluation/regime_breakdown.py
    python evaluation/regime_breakdown.py --results evaluation/results.csv
"""

import argparse
import os
import sys
import numpy as np
import pandas as pd

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
os.chdir(_root)


def improvement(rl, bench):
    """Percent cost reduction of rl relative to bench."""
    if len(rl) == 0 or len(bench) == 0:
        return np.nan
    r, b = rl.mean(), bench.mean()
    return (b - r) / (abs(b) + 1e-9) * 100


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default="evaluation/results.csv")
    parser.add_argument("--benchmarks", default="twap,vwap,ac,pov20")
    parser.add_argument("--min-episodes", type=int, default=25,
                         help="Skip cells with fewer paired episodes than this.")
    args = parser.parse_args()

    df = pd.read_csv(args.results)
    rl_label = "rl" if "rl" in df["strategy"].unique() else "rl_fast"
    benches = [b.strip() for b in args.benchmarks.split(",") if b.strip()]
    benches = [b for b in benches if b in set(df["strategy"].unique())]
    if not benches:
        raise SystemExit(f"None of the requested benchmarks are in {args.results}")

    print(f"Source: {args.results}   ({len(df):,} rows)")
    print(f"Benchmarks: {benches}\n")

    def report(group_col, label, order=None):
        """Compare RL against each benchmark within each level of group_col."""
        if group_col not in df.columns:
            print(f"[{label}] column '{group_col}' not present -- skipped\n")
            return
        levels = order or sorted(df[group_col].dropna().unique())
        print("=" * 74)
        print(label.upper())
        print("=" * 74)
        header = f"{'':>16} | " + " | ".join(f"{b.upper():>8}" for b in benches) + " |     n"
        print(header)
        for side in ["buy", "sell"]:
            print(f"  [{side}]")
            for lv in levels:
                cells, n_used = [], 0
                for b in benches:
                    rl = df[(df.strategy == rl_label) & (df.side == side) &
                            (df[group_col] == lv)]
                    bn = df[(df.strategy == b) & (df.side == side) &
                            (df[group_col] == lv)]
                    # Pair on episode so the comparison is like-for-like
                    m = rl[["episode", "is_bps"]].merge(
                        bn[["episode", "is_bps"]], on="episode",
                        suffixes=("_rl", "_bn"))
                    if len(m) < args.min_episodes:
                        cells.append("     --")
                        continue
                    n_used = max(n_used, len(m))
                    pct = improvement(m["is_bps_rl"], m["is_bps_bn"])
                    cells.append(f"{pct:>+7.1f}%")
                if n_used:
                    print(f"{str(lv):>16} | " + " | ".join(cells) + f" | {n_used:>5}")
        print()

    # 1. Volatility regime, if the backtest recorded it
    report("regime", "By volatility regime")

    # 2. Per ticker, ordered by liquidity so any pattern is visible
    if "ticker" in df.columns:
        liq = (df.groupby("ticker")["avg_participation_rate"].mean()
                 .sort_values(ascending=False).index.tolist()
               if "avg_participation_rate" in df.columns else None)
        report("ticker", "By ticker", order=liq)

    # 3. By how expensive the episode was overall -- does the edge come from
    #    ordinary days or from the difficult tail?
    bench0 = benches[0]
    base = df[df.strategy == bench0][["episode", "is_bps"]].rename(
        columns={"is_bps": "bench_cost"})
    df2 = df.merge(base, on="episode", how="left")
    q = df2["bench_cost"].quantile([0.25, 0.5, 0.75]).values
    def bucket(x):
        if not np.isfinite(x):
            return np.nan
        if x <= q[0]:
            return "1 cheapest"
        if x <= q[1]:
            return "2"
        if x <= q[2]:
            return "3"
        return "4 most expensive"
    df2["difficulty"] = df2["bench_cost"].apply(bucket)
    globals()["df"] = df2
    df = df2
    report("difficulty", f"By episode difficulty (quartiles of {bench0.upper()} cost)",
           order=["1 cheapest", "2", "3", "4 most expensive"])

    print("Reading this: a consistent edge across every cell is stronger than a")
    print("large average driven by one regime, one ticker or the expensive tail.")
    print("Cells marked -- had too few paired episodes to report.")


if __name__ == "__main__":
    main()