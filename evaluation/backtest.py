"""
evaluation/backtest.py — handles buy + sell, SAC model

Usage:
    python evaluation/backtest.py --config configs/default.yaml --model-path models/best_model
"""

import argparse
import sys
import yaml
import numpy as np
import pandas as pd
from pathlib import Path
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

from stable_baselines3 import PPO
from agent.env import ExecutionEnv
from simulator.synthetic_data import u_shaped_volume_profile


def run_episode(env: ExecutionEnv, strategy: str, model=None, side: str = "buy") -> dict:
    # Force a specific side for fair benchmark comparison
    env.default_side = side
    obs, _ = env.reset()
    volume_profile = u_shaped_volume_profile(env.total_steps)
    done = False
    step_slippage = []
    step_participation = []

    while not done:
        if strategy == "rl":
            action, _ = model.predict(obs, deterministic=True)
        elif strategy == "twap":
            action = env.twap_action()
        elif strategy == "vwap":
            action = env.vwap_action(volume_profile)
        elif strategy == "ac":
            action = env.ac_action()
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

        obs, reward, done, _, info = env.step(action)
        step_slippage.append(info.get("slippage_bps", 0))
        step_participation.append(info.get("participation_rate", 0))

    return {
        "strategy": strategy,
        "side": side,
        "total_cost_dollars": env.total_cost,
        "is_bps": env.total_cost / (env.total_shares * env.arrival_price + 1e-9) * 10_000,
        "avg_slippage_bps": float(np.mean(step_slippage)),
        "avg_participation_rate": float(np.mean(step_participation)),
        "unfilled_fraction": env.remaining / env.total_shares,
    }


def run_backtest(cfg, model_path, n_episodes, strategies, seed=12345):
    env = ExecutionEnv(cfg, side="buy")

    model = None
    if "rl" in strategies:
        print(f"Loading SAC model from {model_path}...")
        model = PPO.load(model_path, env=env)

    results = []
    sides = ["buy", "sell"]

    for side in sides:
        for strategy in strategies:
            desc = f"{strategy.upper()} ({side})"
            print(f"\nRunning {desc} — {n_episodes} episodes...")
            for ep in tqdm(range(n_episodes), desc=desc):
                row = run_episode(env, strategy, model=model, side=side)
                row["episode"] = ep
                results.append(row)

    return pd.DataFrame(results)


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--model-path", default="models/best_model")
    parser.add_argument("--n-episodes", type=int, default=None)
    parser.add_argument("--output", default="evaluation/results.csv")
    args = parser.parse_args()

    cfg = load_config(args.config)
    n_episodes = args.n_episodes or cfg["evaluation"]["n_episodes"]
    strategies = cfg["evaluation"]["benchmarks"] + ["rl"]

    df = run_backtest(cfg, args.model_path, n_episodes, strategies)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"\nResults saved to {args.output}")

    print("\n=== Summary by strategy + side ===")
    print(df.groupby(["strategy", "side"])["is_bps"].agg(["mean", "std"]).round(2).to_string())
