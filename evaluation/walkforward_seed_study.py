"""
evaluation/walkforward_seed_study.py

Combines the two validation dimensions that have so far been run
separately: walk-forward folds (out-of-sample in TIME) and training seeds
(robustness to initialisation).

Each fold's models are evaluated against THAT FOLD'S config, so fold 0's
policies are tested on fold 0's held-out window and never on a common one.
seed_variance_study.py cannot do this -- it evaluates several models
against a single config.

Two modes:

  --emit-commands   writes the training commands for every (fold, seed)
                    pair to a file. Run those first; this script does not
                    train anything.

  (default)         evaluates whatever fold/seed models exist and prints
                    the full table plus a summary across folds.

Model naming convention: models/wf_f{fold}_s{seed}.zip

Usage:
    python evaluation/walkforward_seed_study.py --emit-commands --seeds 42,43,44
    python evaluation/walkforward_seed_study.py --seeds 42,43,44 --n-episodes 1000
"""

import argparse
import glob
import os
import sys
import itertools

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


def model_path(fold, seed, prefix="wf"):
    return f"models/{prefix}_f{fold}_s{seed}.zip"


def emit_commands(folds, seeds, timesteps, out_path, prefix="wf"):
    lines = []
    for fold, seed in itertools.product(folds, seeds):
        cfg = f"configs/walkforward/fold{fold}.yaml"
        mdl = model_path(fold, seed, prefix).replace("/", "\\")
        lines.append(
            f"REM ---- fold {fold}, seed {seed} ----\n"
            f"python run.py --config {cfg} --timesteps {timesteps} --train-seed {seed}\n"
            f"copy models\\best_model.zip {mdl}"
        )
    with open(out_path, "w") as f:
        f.write("\n\n".join(lines) + "\n")

    n = len(folds) * len(seeds)
    print(f"Wrote {n} training commands to {out_path}")
    print(f"Estimated ~{n * timesteps / 10_000_000 * 1.6:.1f}h at ~1,985 fps\n")
    print("Copy each model IMMEDIATELY after its run finishes -- run.py")
    print("overwrites models/best_model.zip every time, and a lost baseline")
    print("has already cost this project two retrains.\n")
    print("Then re-run this script without --emit-commands to aggregate.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folds", default="0,1,2,3")
    parser.add_argument("--seeds", default="42,43,44")
    parser.add_argument("--n-episodes", type=int, default=1000)
    parser.add_argument("--eval-seed", type=int, default=99999,
                         help="Held fixed across every model so differences are "
                              "attributable to fold and training seed only.")
    parser.add_argument("--timesteps", type=int, default=10_000_000)
    parser.add_argument("--emit-commands", action="store_true")
    parser.add_argument("--model-prefix", default="wf",
                         help="Model filename prefix, so separate experiments do not "
                              "overwrite each other: models/{prefix}_f{fold}_s{seed}.zip")
    parser.add_argument("--commands-out", default="configs/walkforward/run_wf_seeds.txt")
    parser.add_argument("--output", default="evaluation/walkforward_seed_study.csv")
    args = parser.parse_args()

    folds = [int(f) for f in args.folds.split(",") if f.strip() != ""]
    seeds = [int(s) for s in args.seeds.split(",") if s.strip() != ""]

    if args.emit_commands:
        os.makedirs(os.path.dirname(args.commands_out), exist_ok=True)
        emit_commands(folds, seeds, args.timesteps, args.commands_out, args.model_prefix)
        return

    from evaluation.backtest_fast import run_backtest

    rows = []
    missing = []
    for fold in folds:
        cfg_path = f"configs/walkforward/fold{fold}.yaml"
        if not os.path.exists(cfg_path):
            print(f"fold {fold}: no config at {cfg_path} -- skipped")
            continue
        cfg = load_config(cfg_path)
        strategies = cfg["evaluation"]["benchmarks"]

        for seed in seeds:
            mp = model_path(fold, seed, args.model_prefix)
            if not os.path.exists(mp):
                missing.append(mp)
                continue
            print("=" * 66)
            print(f"fold {fold}, training seed {seed}   ({mp})")
            print("=" * 66)
            df = run_backtest(cfg, mp, args.n_episodes, seed=args.eval_seed)
            rl_label = "rl" if "rl" in df["strategy"].unique() else "rl_fast"

            row = {"fold": fold, "seed": seed}
            for side in ["buy", "sell"]:
                rl = df[(df.strategy == rl_label) & (df.side == side)]["is_bps"].mean()
                for s in strategies:
                    b = df[(df.strategy == s) & (df.side == side)]["is_bps"].mean()
                    pct = (b - rl) / (abs(b) + 1e-9) * 100
                    row[f"{side}|{s}"] = pct
                    print(f"  [{side.upper()}] vs {s.upper():6s}: {pct:+6.1f}%")
            rows.append(row)
            print()

    if missing:
        print(f"Missing {len(missing)} model(s), e.g. {missing[:3]}")
        print("Run with --emit-commands to generate the training commands.\n")
    if not rows:
        raise SystemExit("No models evaluated.")

    out = pd.DataFrame(rows).sort_values(["fold", "seed"]).reset_index(drop=True)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    out.to_csv(args.output, index=False)

    cols = [c for c in out.columns if "|" in c]
    benches = sorted({c.split("|")[1] for c in cols},
                     key=lambda b: [c.split("|")[1] for c in cols].index(b))

    # Per fold: mean across seeds, and the seed spread within that fold
    print("=" * 78)
    print("BY FOLD  (mean across training seeds, ± seed std within fold)")
    print("=" * 78)
    for side in ["buy", "sell"]:
        print(f"\n[{side.upper()}]")
        header = "  fold  | " + " | ".join(f"{b.upper():>13}" for b in benches)
        print(header)
        for fold in sorted(out["fold"].unique()):
            sub = out[out.fold == fold]
            cells = []
            for b in benches:
                v = sub[f"{side}|{b}"].values
                sd = v.std(ddof=1) if len(v) > 1 else 0.0
                cells.append(f"{v.mean():+6.1f} ±{sd:4.1f}")
            print(f"  {fold:>4}  | " + " | ".join(f"{c:>13}" for c in cells))

    # Across everything: the headline a reviewer would want
    print("\n" + "=" * 78)
    print("ACROSS ALL FOLDS AND SEEDS")
    print("=" * 78)
    any_flip = False
    for side in ["buy", "sell"]:
        for b in benches:
            v = out[f"{side}|{b}"].values
            sd = v.std(ddof=1) if len(v) > 1 else 0.0
            flip = (v.min() < 0) and (v.max() > 0)
            any_flip = any_flip or flip
            flag = "  <-- SIGN FLIP" if flip else ""
            print(f"  [{side.upper()}] vs {b.upper():6s}: {v.mean():+6.1f}% ± {sd:4.1f}%  "
                  f"(range {v.min():+6.1f}% to {v.max():+6.1f}%, n={len(v)}){flag}")

    # Separate the two sources of variation, which is the point of the study
    print("\n" + "=" * 78)
    print("VARIANCE DECOMPOSITION")
    print("=" * 78)
    print(f"{'comparison':>22} | {'between folds':>14} | {'within fold':>12}")
    for side in ["buy", "sell"]:
        for b in benches:
            col = f"{side}|{b}"
            fold_means = out.groupby("fold")[col].mean()
            between = fold_means.std(ddof=1) if len(fold_means) > 1 else 0.0
            within = out.groupby("fold")[col].std(ddof=1).mean()
            print(f"{side + ' vs ' + b:>22} | {between:>13.1f}% | {within:>11.1f}%")
    print("\nBetween-fold spread is period dependence -- does the edge survive in")
    print("different market conditions? Within-fold spread is training luck.")
    print("Large between-fold values mean the single-split result was optimistic.")

    print(f"\nSaved to {args.output}")
    if any_flip:
        print("\nWARNING: a comparison flipped sign somewhere in the grid. Report it "
              "as break-even, not a win.")


if __name__ == "__main__":
    main()