"""
evaluation/drawdown_sweep.py

Tests whether the emergency drawdown stop helps or harms.

The stop liquidates everything once accumulated cost exceeds a fraction of
the order's arrival value. The threshold (0.015, i.e. 150bps) was
hand-chosen and never justified.

It is implicated in the worst blowups observed. On a CVX day where the
order was 9.1% of the day's entire volume, TWAP tripped the stop at step
298 and force-filled the remainder for 14,436bps. The RL agent hit the
same day at 19,013bps with an average participation rate of 14.8 -- 1,480%
of a bar's volume, only reachable through force_fill. In both cases the
strategy would very likely have finished more cheaply by continuing to
trade than by emergency-dumping.

That matters beyond one episode: those tail events are what separated two
otherwise identical policies by 33 percentage points in the walk-forward
study (median cost 19.7 vs 18.8 bps, but max 19,013 vs 494).

This sweeps the threshold, including disabling it, and reports both mean
and tail statistics. Evaluation only -- no retraining.

Usage:
    python evaluation/drawdown_sweep.py --model-path models/wf_f3_s43.zip \
        --config configs/walkforward/fold3.yaml
"""

import argparse
import copy
import os
import sys
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
os.chdir(_root)

import numpy as np
import pandas as pd
import yaml

from evaluation.backtest_fast import run_backtest


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--thresholds", default="0.015,0.05,0.15,none",
                         help="Comma-separated fractions of arrival value; "
                              "'none' disables the stop entirely.")
    parser.add_argument("--n-episodes", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=99999)
    parser.add_argument("--output", default="evaluation/drawdown_sweep.csv")
    args = parser.parse_args()

    base = load_config(args.config)
    strategies = base["evaluation"]["benchmarks"]

    vals = []
    for t in args.thresholds.split(","):
        t = t.strip().lower()
        vals.append(None if t in ("none", "null", "off") else float(t))

    print(f"Model: {args.model_path}")
    print(f"Config: {args.config}")
    print(f"Thresholds: {['off' if v is None else v for v in vals]}")
    print(f"{args.n_episodes} episodes each, evaluation seed {args.seed}\n")

    rows = []
    for v in vals:
        cfg = copy.deepcopy(base)
        cfg.setdefault("execution", {})["drawdown_stop_frac"] = v
        label = "off" if v is None else f"{v:.3f}"

        print("=" * 70)
        print(f"drawdown_stop_frac = {label}")
        print("=" * 70)
        df = run_backtest(cfg, args.model_path, args.n_episodes, seed=args.seed)
        rl_label = "rl" if "rl" in df["strategy"].unique() else "rl_fast"

        row = {"threshold": label}
        for side in ["buy", "sell"]:
            rl = df[(df.strategy == rl_label) & (df.side == side)]["is_bps"]
            row[f"rl_mean_{side}"] = rl.mean()
            row[f"rl_median_{side}"] = rl.median()
            row[f"rl_p99_{side}"] = rl.quantile(0.99)
            row[f"rl_max_{side}"] = rl.max()
            for s in strategies:
                b = df[(df.strategy == s) & (df.side == side)]["is_bps"].mean()
                row[f"{side}|{s}"] = (b - rl.mean()) / (abs(b) + 1e-9) * 100

            print(f"  [{side.upper()}] RL cost: mean {rl.mean():7.2f}  "
                  f"median {rl.median():6.2f}  p99 {rl.quantile(0.99):8.2f}  "
                  f"max {rl.max():9.2f}")
            print("           " + "  ".join(
                f"{s.upper()}:{row[f'{side}|{s}']:+.1f}%" for s in strategies))
        rows.append(row)
        print()

    out = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    out.to_csv(args.output, index=False)

    print("=" * 70)
    print("TAIL BEHAVIOUR (the reason this matters)")
    print("=" * 70)
    print(f"{'threshold':>10} | {'side':>5} | {'mean':>8} | {'median':>7} | "
          f"{'p99':>9} | {'max':>10}")
    for _, r in out.iterrows():
        for side in ["buy", "sell"]:
            print(f"{r['threshold']:>10} | {side:>5} | {r[f'rl_mean_{side}']:>8.2f} | "
                  f"{r[f'rl_median_{side}']:>7.2f} | {r[f'rl_p99_{side}']:>9.2f} | "
                  f"{r[f'rl_max_{side}']:>10.2f}")

    print("\n" + "=" * 70)
    print("IMPROVEMENT vs BENCHMARKS BY THRESHOLD")
    print("=" * 70)
    for side in ["buy", "sell"]:
        print(f"\n[{side.upper()}]")
        print("  threshold | " + " | ".join(f"{s.upper():>8}" for s in strategies))
        for _, r in out.iterrows():
            print(f"  {r['threshold']:>9} | " +
                  " | ".join(f"{r[f'{side}|{s}']:>+7.1f}%" for s in strategies))

    print("\nIf the median barely moves while the max falls sharply as the stop is")
    print("loosened, the stop was causing the blowups rather than preventing them.")
    print("Note the benchmarks are affected too -- they share the same stop.")


if __name__ == "__main__":
    main()