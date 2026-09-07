import sys
import os
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
os.chdir(_root)
import argparse
import yaml
import numpy as np
from stable_baselines3 import PPO

from agent.env import ExecutionEnv
from simulator.synthetic_data import load_csv_data
from simulator.data_split import train_test_split_days


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--n-steps", type=int, default=15)
    parser.add_argument("--seed", type=int, default=99999)
    parser.add_argument("--ticker", default=None,
                         help="Force a specific ticker (e.g. DUK, CVX) instead of whatever "
                              "the fixed seed happens to sample -- useful since QQQ (the "
                              "default sample) has near-zero real spread, making cost-based "
                              "reward terms nearly irrelevant regardless of reward shaping.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    data_cfg = cfg["data"]
    exec_cfg = cfg["execution"]
    full_df = load_csv_data(data_cfg["path"], exec_cfg["step_duration_min"])
    test_frac = data_cfg.get("test_frac", 0.2)
    _, test_df = train_test_split_days(full_df, test_frac=test_frac)

    if args.ticker is not None:
        test_df = test_df[test_df["ticker"].str.lower() == args.ticker.lower()].copy()
        if test_df.empty:
            raise SystemExit(f"No rows for ticker '{args.ticker}' in test split.")
        unique_days = sorted(test_df["day"].unique())
        day_map = {old: new for new, old in enumerate(unique_days)}
        test_df["day"] = test_df["day"].map(day_map)
        print(f"Isolated {len(unique_days)} test day(s) for {args.ticker.upper()}")

    print(f"Loading model from {args.model_path}...")
    model = PPO.load(args.model_path.replace(".zip", ""))
    print("Loaded.\n")

    env = ExecutionEnv(cfg, data=test_df, side="sell")
    env.default_urgency = 0.5
    env.reset(seed=args.seed)  # exact same seeding as run_backtest()

    obs, _ = env.reset()
    print(f"Episode start -- ticker={getattr(env, 'ticker', None)}, total_shares={env.total_shares}\n")
    print(f"{'step':>4} | {'raw_action':>12} | {'remaining_before':>16} | "
          f"{'qty_requested':>14} | {'filled_qty':>12} | {'part_rate':>10}")
    for step in range(args.n_steps):
        pre_remaining = env.remaining
        action, _ = model.predict(obs, deterministic=True)
        a = float(np.clip(action[0], 0.0, 1.0))

        # Compute the requested quantity the way the ACTIVE action mode does.
        # Reporting action * remaining under participation_rate would be
        # badly misleading -- it would show ~100k "requested" when the agent
        # actually asked for action * max_participation_rate * step_volume.
        step_volume = float(env.sim.day_data.loc[env.sim.step_idx, "volume"])
        if getattr(env, "action_mode", "fraction_of_remaining") == "participation_rate":
            qty_requested = min(a * env.market_cfg.max_participation_rate * step_volume,
                                 pre_remaining)
        else:
            qty_requested = a * pre_remaining

        obs, reward, done, _, info = env.step(action)
        filled = pre_remaining - info["remaining"]
        part_rate = filled / step_volume if step_volume > 0 else 0.0
        print(f"{step:>4} | {action[0]:>12.6f} | {pre_remaining:>16.1f} | "
              f"{qty_requested:>14.1f} | {filled:>12.1f} | {part_rate:>10.4f}")
        if done:
            break


if __name__ == "__main__":
    main()