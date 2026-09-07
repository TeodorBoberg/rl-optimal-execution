"""
evaluation/seed_variance_study.py

Quantifies TRAINING-seed variance: how much does the final result depend on
the random seed used during training, holding data and config fixed?

This is distinct from what backtest_repeated.py measures. That varies the
EVALUATION seed (which episodes get sampled) against ONE trained policy.
This varies the TRAINING seed, producing genuinely different policies, and
asks whether the headline improvement is a property of the method or of one
lucky training run. It is the gap a quant audience notices fastest.

Each model is evaluated with the SAME fixed evaluation seed and episode
count, so any spread across models is attributable to training, not to
evaluation sampling.

Usage:
    python evaluation/seed_variance_study.py --models models/seed42.zip,models/seed43.zip,models/seed44.zip
    python evaluation/seed_variance_study.py --models models/seed42.zip,models/seed43.zip --n-episodes 3000
"""

import sys
import os
import argparse
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


def improvements(df, strategies, rl_label="rl_fast"):
    out = {}
    for side in ["buy", "sell"]:
        rl = df[(df.strategy == rl_label) & (df.side == side)]["is_bps"].mean()
        for s in strategies:
            bench = df[(df.strategy == s) & (df.side == side)]["is_bps"].mean()
            out[(side, s)] = (bench - rl) / (abs(bench) + 1e-9) * 100
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--models", required=True,
                         help="Comma-separated model paths, one per training seed.")
    parser.add_argument("--n-episodes", type=int, default=1000)
    parser.add_argument("--eval-seed", type=int, default=99999,
                         help="FIXED across all models, so differences are attributable "
                              "to training seed rather than evaluation sampling.")
    parser.add_argument("--output", default="evaluation/seed_variance_summary.csv")
    args = parser.parse_args()

    cfg = load_config(args.config)
    strategies = cfg["evaluation"]["benchmarks"]
    model_paths = [m.strip() for m in args.models.split(",") if m.strip()]

    missing = [m for m in model_paths if not os.path.exists(m)]
    if missing:
        raise SystemExit(f"Model file(s) not found: {missing}")

    print(f"Training-seed variance study over {len(model_paths)} model(s)")
    print(f"Evaluation held fixed: seed={args.eval_seed}, n_episodes={args.n_episodes}\n")

    rows = []
    for path in model_paths:
        print("=" * 60)
        print(f"Evaluating {path}")
        print("=" * 60)
        df = run_backtest(cfg, path, args.n_episodes, seed=args.eval_seed)
        imp = improvements(df, strategies)
        imp["model"] = os.path.basename(path)
        rows.append(imp)
        for side in ["buy", "sell"]:
            for s in strategies:
                print(f"  [{side.upper()}] RL vs {s.upper()}: {imp[(side, s)]:+.1f}%")
        print()

    runs = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    runs.to_csv(args.output, index=False)

    print("=" * 60)
    print(f"TRAINING-SEED VARIANCE across {len(model_paths)} independently trained policies")
    print("=" * 60)
    any_flip = False
    for side in ["buy", "sell"]:
        for s in strategies:
            vals = runs[(side, s)].values
            mean = vals.mean()
            std = vals.std(ddof=1) if len(vals) > 1 else 0.0
            flip = (vals.min() < 0) and (vals.max() > 0)
            any_flip = any_flip or flip
            flag = "  <-- SIGN FLIP ACROSS TRAINING SEEDS" if flip else ""
            print(f"  [{side.upper()}] RL vs {s.upper()}: {mean:+.1f}% +/- {std:.1f}%  "
                  f"(range {vals.min():+.1f}% to {vals.max():+.1f}%){flag}")

    print(f"\nPer-model results saved to {args.output}")
    if any_flip:
        print("\nWARNING: at least one comparison flipped sign across TRAINING seeds. "
              "That means the result depends materially on training luck, and the "
              "headline number should be reported as a distribution, not a point estimate.")
    else:
        print("\nNo sign flips across training seeds -- the improvement is a property "
              "of the method, not of one lucky training run.")
        print("Report the headline as mean +/- std across training seeds for full rigour.")


if __name__ == "__main__":
    main()