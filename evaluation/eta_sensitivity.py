"""
evaluation/eta_sensitivity.py

Tests whether benchmark rankings -- specifically POV 20% beating the RL
policy on buys -- are robust to the market impact magnitude, which is the
one major cost parameter that is NOT calibrated from data.

Context: impact_exponent (0.65) was validated against 11.75M real
Lee-Ready-classified trades, but eta_temporary (the absolute LEVEL of
temporary impact) could not be. Real tape prints are far too small to
observe impact at institutional participation rates -- only 31 of 10.5M
classified trades exceeded ~1% participation -- so eta_temporary remains
at its original assumed value. If true impact is higher than modelled,
aggressive strategies like POV 20% are being systematically flattered.

IMPORTANT ASYMMETRY: the RL policy was TRAINED at the baseline eta. The
benchmarks are rule-based and carry no such dependency. Raising eta at
evaluation time therefore handicaps the RL agent specifically -- it is
optimising for an impact level that no longer applies. This makes the
test CONSERVATIVE: if the RL policy closes the gap on POV 20% anyway,
that is strong evidence the gap was an artifact of low modelled impact.
If it does not close, the result is ambiguous between "POV 20% is
genuinely robust" and "the RL policy is simply mismatched to the
evaluation environment".

Usage:
    python evaluation/eta_sensitivity.py --model-path models/best_model_FINAL.zip
    python evaluation/eta_sensitivity.py --model-path models/best_model_FINAL.zip --multipliers 1,2,5,10
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

from evaluation.backtest_fast import run_backtest


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--multipliers", default="1,2,5,10",
                         help="Comma-separated multipliers applied to market.eta_temporary.")
    parser.add_argument("--n-episodes", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=99999)
    parser.add_argument("--output", default="evaluation/eta_sensitivity.csv")
    args = parser.parse_args()

    base_cfg = load_config(args.config)
    strategies = base_cfg["evaluation"]["benchmarks"]
    base_eta = base_cfg["market"]["eta_temporary"]
    mults = [float(m) for m in args.multipliers.split(",")]

    print(f"Baseline eta_temporary = {base_eta}")
    print(f"Testing multipliers: {mults}")
    print(f"{args.n_episodes} episodes per setting, evaluation seed fixed at {args.seed}\n")
    print("NOTE: the RL policy was trained at the BASELINE eta. Higher multipliers")
    print("handicap it relative to the rule-based benchmarks, so this test is")
    print("conservative -- see module docstring.\n")

    rows = []
    for mult in mults:
        cfg = copy.deepcopy(base_cfg)
        cfg["market"]["eta_temporary"] = base_eta * mult
        print("=" * 70)
        print(f"eta_temporary = {base_eta * mult:.6f}  ({mult}x baseline)")
        print("=" * 70)

        df = run_backtest(cfg, args.model_path, args.n_episodes, seed=args.seed)
        rl_label = "rl" if "rl" in df["strategy"].unique() else "rl_fast"

        row = {"eta_multiplier": mult, "eta": base_eta * mult}
        for side in ["buy", "sell"]:
            rl_cost = df[(df.strategy == rl_label) & (df.side == side)]["is_bps"].mean()
            row[f"rl_cost_{side}"] = rl_cost
            for s in strategies:
                bench = df[(df.strategy == s) & (df.side == side)]["is_bps"].mean()
                pct = (bench - rl_cost) / (abs(bench) + 1e-9) * 100
                row[f"{side}_vs_{s}"] = pct
                row[f"{side}_cost_{s}"] = bench
                print(f"  [{side.upper()}] RL vs {s.upper():6s}: {pct:+6.1f}%   "
                      f"(RL {rl_cost:7.2f} bps vs {bench:7.2f} bps)")
        rows.append(row)
        print()

    out = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    out.to_csv(args.output, index=False)

    # Focused summary: how does each comparison move as impact rises?
    print("=" * 70)
    print("TREND: improvement (%) vs eta multiplier")
    print("=" * 70)
    header = "  " + "benchmark".ljust(14) + "".join(f"{m:>10.0f}x" for m in mults)
    for side in ["buy", "sell"]:
        print(f"\n[{side.upper()}]")
        print(header)
        for s in strategies:
            vals = [r[f"{side}_vs_{s}"] for r in rows]
            line = "  " + s.ljust(14) + "".join(f"{v:>10.1f}" for v in vals)
            trend = vals[-1] - vals[0]
            line += f"   ({trend:+.1f} pts across range)"
            print(line)

    print(f"\nSaved to {args.output}")
    print("\nReading this: if RL-vs-POV20 rises with eta, POV 20%'s advantage at the")
    print("baseline was an artifact of low modelled impact. If it stays flat or falls,")
    print("POV 20% is robust -- but recall the training-mismatch caveat above.")


if __name__ == "__main__":
    main()