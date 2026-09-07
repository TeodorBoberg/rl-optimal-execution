"""
evaluation/passive_sensitivity.py

Tests how much of the passive-execution improvement survives pessimistic
assumptions about the two parameters driving it, neither of which is
calibrated:

    market.passive_fill_prob      0.4     probability a resting order fills
                                          within a step, before size and
                                          volatility adjustments
    fees.maker_rebate_per_share   0.0020  rebate earned per passive share

passive_fill_prob cannot be estimated from the tape at all: the tape
records executions, not resting orders that never filled. It is therefore
the single largest untested assumption behind the ~10-13 point gain that
passive execution produced.

IMPORTANT ASYMMETRY, same as the eta sweep: the policy was TRAINED at
passive_fill_prob = 0.4. Evaluating it at 0.2 handicaps it specifically --
it will keep resting orders that no longer fill at the rate it learned to
expect, and pay for the resulting backlog at the close. The benchmarks are
pure-aggressive and completely unaffected by either parameter, so they
provide a fixed reference. This makes the test CONSERVATIVE: a gain that
survives here is real, but a gain that disappears may be recoverable by
retraining at the lower fill rate.

Usage:
    python evaluation/passive_sensitivity.py --model-path models/best_model_PASSIVE.zip
    python evaluation/passive_sensitivity.py --model-path models/best_model_PASSIVE.zip --fill-probs 0.1,0.2,0.3,0.4 --rebates 0.0,0.001,0.002
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
    parser.add_argument("--fill-probs", default="0.1,0.2,0.3,0.4,0.5")
    parser.add_argument("--rebates", default="",
                         help="Optional second sweep over maker_rebate_per_share, "
                              "run at the baseline fill probability.")
    parser.add_argument("--n-episodes", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=99999)
    parser.add_argument("--output", default="evaluation/passive_sensitivity.csv")
    args = parser.parse_args()

    base = load_config(args.config)
    strategies = base["evaluation"]["benchmarks"]
    base_fp = base.get("market", {}).get("passive_fill_prob", 0.4)
    base_rb = base.get("fees", {}).get("maker_rebate_per_share", 0.0)

    if not base.get("execution", {}).get("enable_passive", False):
        raise SystemExit("execution.enable_passive is false in this config -- "
                          "there is no passive execution to test.")

    fps = [float(x) for x in args.fill_probs.split(",") if x.strip()]
    rbs = [float(x) for x in args.rebates.split(",") if x.strip()]

    print(f"Baseline: passive_fill_prob={base_fp}, maker_rebate_per_share={base_rb}")
    print(f"Policy was TRAINED at the baseline; lower fill probabilities handicap "
          f"it relative to the pure-aggressive benchmarks.\n")

    rows = []

    def run(label, cfg, tag):
        print("=" * 68)
        print(label)
        print("=" * 68)
        df = run_backtest(cfg, args.model_path, args.n_episodes, seed=args.seed)
        rl_label = "rl" if "rl" in df["strategy"].unique() else "rl_fast"
        row = dict(tag)
        for side in ["buy", "sell"]:
            rl = df[(df.strategy == rl_label) & (df.side == side)]["is_bps"].mean()
            row[f"rl_cost_{side}"] = rl
            for s in strategies:
                b = df[(df.strategy == s) & (df.side == side)]["is_bps"].mean()
                pct = (b - rl) / (abs(b) + 1e-9) * 100
                row[f"{side}_vs_{s}"] = pct
                print(f"  [{side.upper()}] RL vs {s.upper():6s}: {pct:+6.1f}%   "
                      f"(RL {rl:7.2f} vs {b:7.2f} bps)")
        rows.append(row)
        print()

    for fp in fps:
        cfg = copy.deepcopy(base)
        cfg.setdefault("market", {})["passive_fill_prob"] = fp
        run(f"passive_fill_prob = {fp}   (baseline {base_fp})",
            cfg, {"sweep": "fill_prob", "fill_prob": fp, "rebate": base_rb})

    for rb in rbs:
        cfg = copy.deepcopy(base)
        cfg.setdefault("fees", {})["maker_rebate_per_share"] = rb
        run(f"maker_rebate_per_share = {rb}   (baseline {base_rb})",
            cfg, {"sweep": "rebate", "fill_prob": base_fp, "rebate": rb})

    out = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    out.to_csv(args.output, index=False)

    for sweep, var, vals in [("fill_prob", "fill_prob", fps), ("rebate", "rebate", rbs)]:
        sub = out[out["sweep"] == sweep]
        if sub.empty:
            continue
        print("=" * 68)
        print(f"TREND: improvement (%) vs {var}")
        print("=" * 68)
        header = "  " + "benchmark".ljust(12) + "".join(f"{v:>10}" for v in vals)
        for side in ["buy", "sell"]:
            print(f"\n[{side.upper()}]")
            print(header)
            for s in strategies:
                series = [sub[sub[var] == v][f"{side}_vs_{s}"].iloc[0] for v in vals]
                line = "  " + s.ljust(12) + "".join(f"{x:>10.1f}" for x in series)
                print(line + f"   ({series[-1]-series[0]:+.1f} pts)")

    print(f"\nSaved to {args.output}")
    print("\nReading this: the gain from passive execution is real only to the extent")
    print("it survives at pessimistic fill rates. If improvements collapse below")
    print("fill_prob 0.2-0.3, the headline depends on an assumption that cannot be")
    print("verified from tape data, and should be presented with that caveat.")


if __name__ == "__main__":
    main()