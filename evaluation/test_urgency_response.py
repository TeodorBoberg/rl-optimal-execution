"""
evaluation/test_urgency_response.py

Direct test of urgency conditioning: for each urgency level, measure WHEN
the order actually completes and how execution is distributed across the
day. This is a far sharper test than reading raw_action, because once the
order is filled the raw action is meaningless (there is nothing left to
trade, so any value produces a zero fill).

If urgency works, patient (0.0) should complete meaningfully later and
spread execution more evenly than urgent (1.0).

Usage:
    python evaluation/test_urgency_response.py --model-path models/best_model.zip
    python evaluation/test_urgency_response.py --model-path models/best_model.zip --tickers CVX,NVDA,SPY
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
from stable_baselines3 import PPO

from agent.env import ExecutionEnv
from simulator.synthetic_data import load_csv_data
from simulator.data_split import train_test_split_days


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def run_episode(env, predict_fn, urgency):
    env.default_urgency = urgency
    obs, _ = env.reset()
    total = env.total_shares
    filled_cumsum = []
    completion_step = None
    done = False
    step = 0
    while not done:
        action = predict_fn(obs)
        obs, _, done, _, info = env.step(action)
        filled_frac = 1.0 - (info["remaining"] / total)
        filled_cumsum.append(filled_frac)
        if completion_step is None and filled_frac >= 0.999:
            completion_step = step
        step += 1
    if completion_step is None:
        completion_step = step - 1
    return np.array(filled_cumsum), completion_step, info["is_bps"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--tickers", default="CVX,NVDA,SPY")
    parser.add_argument("--n-episodes", type=int, default=10)
    parser.add_argument("--side", default="sell", choices=["buy", "sell"])
    parser.add_argument("--seed", type=int, default=99999)
    args = parser.parse_args()

    cfg = load_config(args.config)
    data_cfg, exec_cfg = cfg["data"], cfg["execution"]
    full_df = load_csv_data(data_cfg["path"], exec_cfg["step_duration_min"])
    _, test_df = train_test_split_days(full_df, test_frac=data_cfg.get("test_frac", 0.2))

    model = PPO.load(args.model_path.replace(".zip", ""))

    def predict_fn(obs):
        a, _ = model.predict(obs, deterministic=True)
        return a

    total_steps = exec_cfg["total_steps"]
    print(f"\nAction mode: {exec_cfg.get('action_mode', 'fraction_of_remaining')}")
    print(f"Order sizing: {'%.1f%% of ADV' % (exec_cfg['order_size_pct_adv']*100) if exec_cfg.get('order_size_pct_adv') else '%d shares fixed' % exec_cfg['total_shares']}")
    print(f"Side: {args.side}, {args.n_episodes} episodes per (ticker, urgency)\n")

    for tk in [t.strip() for t in args.tickers.split(",")]:
        sub = test_df[test_df["ticker"].str.lower() == tk.lower()].copy()
        if sub.empty:
            print(f"{tk}: not in test split, skipping")
            continue
        days = sorted(sub["day"].unique())
        sub["day"] = sub["day"].map({d: i for i, d in enumerate(days)})

        print(f"=== {tk.upper()} ===")
        print(f"{'urgency':>8} | {'completion step':>15} | {'% done by 25%':>13} | "
              f"{'% done by 50%':>13} | {'mean is_bps':>11}")
        for urgency in [0.0, 0.25, 0.5, 0.75, 1.0]:
            env = ExecutionEnv(cfg, data=sub, side=args.side, urgency=urgency)
            env.reset(seed=args.seed)
            comps, q25s, q50s, costs = [], [], [], []
            for _ in range(args.n_episodes):
                curve, comp, cost = run_episode(env, predict_fn, urgency)
                comps.append(comp)
                q25s.append(curve[int(0.25 * total_steps)] if len(curve) > int(0.25*total_steps) else 1.0)
                q50s.append(curve[int(0.50 * total_steps)] if len(curve) > int(0.50*total_steps) else 1.0)
                costs.append(cost)
            print(f"{urgency:>8.2f} | {np.mean(comps):>15.1f} | {np.mean(q25s):>12.1%} | "
                  f"{np.mean(q50s):>12.1%} | {np.mean(costs):>11.2f}")
        print()

    print("Reading this: if urgency conditioning works, completion step should INCREASE")
    print("and '% done by 25%' should DECREASE as urgency goes from 1.0 down to 0.0.")
    print("Identical rows across urgency levels means urgency is being ignored.")


if __name__ == "__main__":
    main()