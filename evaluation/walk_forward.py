"""
evaluation/walk_forward.py

Walk-forward validation: instead of one fixed chronological split, train and
test over several rolling windows moving through time.

Why it matters: the current result comes from ONE split (394 train days /
99 test days per ticker). That tests the policy in one market period. If
that period happened to suit the strategy, the result is optimistic and
there is no way to tell from a single split. Walk-forward re-trains on each
successive window and tests on the period immediately after, which is how
the strategy would actually be deployed.

Fold structure (expanding-window by default):
    fold 0: train days [0, T0)          test days [T0, T0+H)
    fold 1: train days [0, T0+H)        test days [T0+H, T0+2H)
    ...
Use --rolling for a fixed-width training window instead, which tests
whether older data helps or hurts.

This script GENERATES the fold configs and the commands to run. It does not
train them itself: each fold is a full training run (~8h), so they need to
be run deliberately rather than kicked off by accident.

Usage:
    python evaluation/walk_forward.py --n-folds 4
    python evaluation/walk_forward.py --n-folds 4 --rolling --train-days 250
"""

import sys
import os
import argparse
import copy
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
os.chdir(_root)

import numpy as np
import pandas as pd
import yaml


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--n-folds", type=int, default=4)
    parser.add_argument("--test-days", type=int, default=60,
                         help="Test window length per fold, in trading days per ticker.")
    parser.add_argument("--min-train-days", type=int, default=200,
                         help="Training days in the first fold.")
    parser.add_argument("--rolling", action="store_true",
                         help="Fixed-width training window instead of expanding.")
    parser.add_argument("--train-days", type=int, default=250,
                         help="Training window width when --rolling is set.")
    parser.add_argument("--output-dir", default="configs/walkforward")
    parser.add_argument("--data-dir", default="data/walkforward")
    args = parser.parse_args()

    cfg = load_config(args.config)
    src = cfg["data"]["path"]
    df = pd.read_csv(src)
    if "ticker" not in df.columns:
        raise SystemExit("Data has no ticker column.")

    days_per_ticker = df.groupby("ticker")["day"].nunique()
    n_days = int(days_per_ticker.min())
    print(f"Source: {src}")
    print(f"{len(days_per_ticker)} tickers, {n_days} days each (min)\n")

    needed = args.min_train_days + args.n_folds * args.test_days
    if needed > n_days:
        raise SystemExit(
            f"Not enough days: need {needed} "
            f"({args.min_train_days} train + {args.n_folds} x {args.test_days} test) "
            f"but only {n_days} available. Reduce --n-folds or --test-days.")

    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.data_dir, exist_ok=True)

    print(f"{'fold':>5} | {'train days':>20} | {'test days':>14} | files")
    commands = []
    for k in range(args.n_folds):
        test_start = args.min_train_days + k * args.test_days
        test_end = test_start + args.test_days
        train_start = 0 if not args.rolling else max(0, test_start - args.train_days)

        # Slice per ticker, then renumber days contiguously within each split
        # (everything downstream assumes contiguous 0..n-1 day indices).
        train_parts, test_parts = [], []
        for tk, g in df.groupby("ticker", sort=False):
            days = np.sort(g["day"].unique())
            tr = days[train_start:test_start]
            te = days[test_start:test_end]
            train_parts.append(g[g["day"].isin(tr)])
            test_parts.append(g[g["day"].isin(te)])

        fold_df = pd.concat(train_parts + test_parts, ignore_index=True)
        # Renumber globally, keeping ticker blocks contiguous and chronological
        out = []
        offset = 0
        for tk, g in fold_df.groupby("ticker", sort=False):
            g = g.copy()
            remap = {d: i + offset for i, d in enumerate(np.sort(g["day"].unique()))}
            g["day"] = g["day"].map(remap)
            offset = g["day"].max() + 1
            out.append(g)
        fold_df = pd.concat(out, ignore_index=True)

        data_path = os.path.join(args.data_dir, f"fold{k}.csv").replace("\\", "/")
        fold_df.to_csv(data_path, index=False)

        # test_frac is applied per ticker by train_test_split_days, so express
        # the test window as a fraction of this fold's total days per ticker.
        fold_days = (test_end - train_start)
        test_frac = args.test_days / fold_days

        fold_cfg = copy.deepcopy(cfg)
        fold_cfg["data"]["path"] = data_path
        fold_cfg["data"]["test_frac"] = round(test_frac, 6)
        cfg_path = os.path.join(args.output_dir, f"fold{k}.yaml").replace("\\", "/")
        with open(cfg_path, "w") as f:
            yaml.safe_dump(fold_cfg, f, sort_keys=False)

        print(f"{k:>5} | {train_start:>6}-{test_start:<13} | "
              f"{test_start:>5}-{test_end:<8} | {os.path.basename(cfg_path)}")

        commands.append(
            f"python run.py --config {cfg_path} --timesteps 10000000\n"
            f"copy models\\best_model.zip models\\wf_fold{k}.zip\n"
            f"python evaluation\\backtest_repeated.py --config {cfg_path} "
            f"--model-path models\\wf_fold{k}.zip --n-runs 3 --n-episodes 1000"
        )

    script = os.path.join(args.output_dir, "run_all_folds.txt")
    with open(script, "w") as f:
        f.write("\n\n".join(commands) + "\n")

    print(f"\nFold configs written to {args.output_dir}/")
    print(f"Fold datasets written to {args.data_dir}/")
    print(f"Commands written to {script}")
    print(f"\nEach fold is a full training run. {args.n_folds} folds at ~8h each "
          f"= ~{args.n_folds * 8}h total.")
    print("\nWhat to look for: consistent improvement ACROSS folds. If fold 0 shows")
    print("+25% and fold 3 shows +5%, the edge is period-dependent and the single-split")
    print("result was optimistic. Stable numbers across folds are much stronger evidence")
    print("than one split, because each fold tests a genuinely out-of-sample period.")


if __name__ == "__main__":
    main()