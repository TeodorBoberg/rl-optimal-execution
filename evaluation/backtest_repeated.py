"""
evaluation/backtest_repeated.py

Runs the backtest multiple times with different seeds and reports
mean +/- std of the RL-vs-benchmark improvement percentages, instead
of a single run's numbers. A single run's improvement % is one draw
from a distribution with real variance (different random days/tickers
get sampled each time) -- this script quantifies that variance so you
can report a stable, defensible number instead of whichever run you
happened to paste last.

Usage:
    python evaluation/backtest_repeated.py --config configs/default.yaml --n-runs 5
    python evaluation/backtest_repeated.py --config configs/default.yaml --n-runs 5 --n-episodes 100
"""

import argparse
import sys
import os
import yaml
import numpy as np
import pandas as pd
from pathlib import Path

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
os.chdir(_root)

from evaluation.backtest_fast import run_backtest


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def compute_improvements(df: pd.DataFrame, strategies, rl_label="rl_fast") -> dict:
    """Return {(side, strategy): pct_improvement} for one run's results df."""
    out = {}
    for side in ["buy", "sell"]:
        rl = df[(df["strategy"] == rl_label) & (df["side"] == side)]["is_bps"].mean()
        for strategy in strategies:
            bench = df[(df["strategy"] == strategy) & (df["side"] == side)]["is_bps"].mean()
            diff = bench - rl
            pct = diff / (abs(bench) + 1e-9) * 100
            out[(side, strategy)] = pct
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config",     default="configs/default.yaml")
    parser.add_argument("--model-path", default="models/best_model.zip")
    parser.add_argument("--n-episodes", type=int, default=None)
    parser.add_argument("--n-runs",     type=int, default=5)
    parser.add_argument("--base-seed",  type=int, default=99999)
    parser.add_argument("--output",     default="evaluation/results_repeated_summary.csv")
    args = parser.parse_args()

    cfg = load_config(args.config)
    n_episodes = args.n_episodes or cfg["evaluation"]["n_episodes"]
    strategies = cfg["evaluation"]["benchmarks"]

    all_runs = []  # list of dicts: {(side, strategy): pct}
    for i in range(args.n_runs):
        seed = args.base_seed + i
        print("\n" + "=" * 60)
        print(f"RUN {i + 1}/{args.n_runs}  (seed={seed})")
        print("=" * 60)
        df = run_backtest(cfg, args.model_path, n_episodes, seed=seed)
        improvements = compute_improvements(df, strategies)
        improvements["seed"] = seed
        all_runs.append(improvements)

        for side in ["buy", "sell"]:
            for strategy in strategies:
                pct = improvements[(side, strategy)]
                print(f"  [{side.upper()}] RL vs {strategy.upper()}: {pct:+.1f}%")

    # ---- Aggregate across runs ----
    runs_df = pd.DataFrame(all_runs)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    runs_df.to_csv(args.output, index=False)

    print("\n" + "=" * 60)
    print(f"SUMMARY across {args.n_runs} runs (seeds {args.base_seed}..{args.base_seed + args.n_runs - 1})")
    print("=" * 60)
    any_sign_flip = False
    for side in ["buy", "sell"]:
        for strategy in strategies:
            col = (side, strategy)
            vals = runs_df[col].values
            mean, std = vals.mean(), vals.std(ddof=1) if len(vals) > 1 else 0.0
            min_v, max_v = vals.min(), vals.max()
            flip = (min_v < 0) and (max_v > 0)
            if flip:
                any_sign_flip = True
            flag = "  <-- SIGN FLIP ACROSS RUNS" if flip else ""
            print(f"  [{side.upper()}] RL vs {strategy.upper()}: {mean:+.1f}% +/- {std:.1f}%  "
                  f"(range {min_v:+.1f}% to {max_v:+.1f}%){flag}")

    # ---- Presentation-ready markdown table ----
    md_path = args.output.replace(".csv", "_table.md")
    with open(md_path, "w") as f:
        f.write(f"# Backtest results across {args.n_runs} runs "
                f"(seeds {args.base_seed}-{args.base_seed + args.n_runs - 1}, "
                f"{n_episodes} episodes/run)\n\n")
        f.write("| Side | vs Benchmark | Mean Improvement | Std Dev | Range |\n")
        f.write("|---|---|---|---|---|\n")
        for side in ["buy", "sell"]:
            for strategy in strategies:
                col = (side, strategy)
                vals = runs_df[col].values
                mean, std = vals.mean(), vals.std(ddof=1) if len(vals) > 1 else 0.0
                min_v, max_v = vals.min(), vals.max()
                f.write(f"| {side.upper()} | {strategy.upper()} | {mean:+.1f}% | "
                        f"±{std:.1f}% | {min_v:+.1f}% to {max_v:+.1f}% |\n")
    print(f"Presentation-ready table saved to {md_path}")

    print(f"\nPer-run results saved to {args.output}")
    if any_sign_flip:
        print("\nWARNING: at least one comparison flipped sign (improvement vs worse) "
              "across different seeds. Do not present that comparison as a reliable "
              "win until investigated further.")
    else:
        print("\nNo sign flips across runs -- all comparisons directionally consistent.")


if __name__ == "__main__":
    main()