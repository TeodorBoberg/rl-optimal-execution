"""
evaluation/debug_blowup.py

Finds a catastrophic benchmark episode (participation >> 1, cost in the
thousands of bps) and prints it step by step, so the failure mechanism is
observed rather than inferred.

Ruled out already for fold0: fee changes, config mismatch between fold and
default, per-ticker ADV shift, order feasibility (zero infeasible test
days), short/malformed ticker-days. Medians are normal and only a handful
of episodes explode, so this reproduces those specific episodes.

Usage:
    python evaluation/debug_blowup.py --config configs/walkforward/fold0.yaml --strategy twap --side buy
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

from agent.env import ExecutionEnv
from simulator.synthetic_data import load_csv_data, load_empirical_volume_profile
from simulator.data_split import train_test_split_days


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/walkforward/fold0.yaml")
    parser.add_argument("--strategy", default="twap", choices=["twap", "vwap", "ac"])
    parser.add_argument("--side", default="buy", choices=["buy", "sell"])
    parser.add_argument("--n-episodes", type=int, default=200)
    parser.add_argument("--seed", type=int, default=99999)
    parser.add_argument("--threshold-bps", type=float, default=1000.0)
    args = parser.parse_args()

    cfg = load_config(args.config)
    d, e = cfg["data"], cfg["execution"]
    full = load_csv_data(d["path"], e["step_duration_min"])
    _, test_df = train_test_split_days(full, test_frac=d.get("test_frac", 0.2))

    env = ExecutionEnv(cfg, data=test_df, side=args.side)
    env.reset(seed=args.seed)   # same seeding as run_backtest
    profile = load_empirical_volume_profile(n_steps=env.total_steps)

    print(f"\nScanning {args.n_episodes} {args.strategy.upper()} {args.side} episodes "
          f"for cost > {args.threshold_bps} bps...\n")

    worst = None
    for ep in range(args.n_episodes):
        env.default_side = args.side
        obs, _ = env.reset()
        ticker = getattr(env, "ticker", None)
        total = env.total_shares
        rows = []
        done = False
        step = 0
        while not done:
            if args.strategy == "twap":
                a = env.twap_action()
            elif args.strategy == "vwap":
                a = env.vwap_action(profile)
            else:
                a = env.ac_action()
            pre = env.remaining
            sv = float(env.sim.day_data.loc[env.sim.step_idx, "volume"])
            obs, _, done, _, info = env.step(a)
            rows.append({
                "step": step, "action": float(a[0]), "step_volume": sv,
                "remaining_before": pre, "filled": pre - info["remaining"],
                "part_rate": (pre - info["remaining"]) / sv if sv > 0 else np.nan,
                "step_cost_bps": info["step_cost"] / (env.arrival_price * total + 1e-9) * 1e4,
                "cum_bps": info["is_bps"], "drawdown_stop": info["drawdown_stop"],
            })
            step += 1
        cost = info["is_bps"]
        if cost > args.threshold_bps and (worst is None or cost > worst[1]):
            worst = (ep, cost, ticker, total, pd.DataFrame(rows))

    if worst is None:
        print(f"No episode exceeded {args.threshold_bps} bps. "
              f"Try more episodes or a different strategy/side.")
        return

    ep, cost, ticker, total, tr = worst
    print(f"WORST EPISODE: #{ep}, ticker={ticker}, order={total:,.0f} shares, "
          f"final cost={cost:,.1f} bps\n")

    print("Day volume profile for this episode:")
    print(f"  total day volume = {tr['step_volume'].sum():,.0f}")
    print(f"  min/median/max per-step volume = {tr['step_volume'].min():,.0f} / "
          f"{tr['step_volume'].median():,.0f} / {tr['step_volume'].max():,.0f}")
    print(f"  order as % of day volume = {total / max(tr['step_volume'].sum(), 1):.1%}")

    dd = tr[tr["drawdown_stop"]]
    if len(dd):
        print(f"\n  DRAWDOWN STOP fired first at step {int(dd['step'].iloc[0])}")

    big = tr.nlargest(5, "part_rate")
    print("\nSteps with the highest participation:")
    print(big[["step", "action", "step_volume", "remaining_before", "filled",
               "part_rate", "step_cost_bps", "cum_bps"]].round(3).to_string(index=False))

    print("\nFirst 8 steps:")
    print(tr.head(8)[["step", "action", "step_volume", "remaining_before", "filled",
                       "part_rate", "cum_bps"]].round(3).to_string(index=False))
    print("\nLast 5 steps:")
    print(tr.tail(5)[["step", "action", "step_volume", "remaining_before", "filled",
                       "part_rate", "step_cost_bps", "cum_bps"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()