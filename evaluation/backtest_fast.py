"""
evaluation/backtest_fast.py

Evaluates the fast PPO model against TWAP/VWAP/AC benchmarks.

Usage:
    python evaluation/backtest_fast.py --config configs/default.yaml
    python evaluation/backtest_fast.py --config configs/default.yaml --model-path models/fast_model_best.pt
"""

import argparse
import sys
import yaml
import numpy as np
import pandas as pd
from pathlib import Path
from tqdm import tqdm

import os
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
# Also ensure simulator is findable when agent.env imports it
os.chdir(_root)

import torch
from stable_baselines3 import PPO
from agent.env import ExecutionEnv
from simulator.synthetic_data import u_shaped_volume_profile, load_empirical_volume_profile, load_csv_data, generate_intraday_data, SyntheticMarketConfig
from simulator.data_split import train_test_split_days


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def run_benchmark_episode(env: ExecutionEnv, strategy: str, side: str) -> dict:
    """Run one episode of a classical benchmark."""
    env.default_side = side
    obs, _ = env.reset()
    volume_profile = load_empirical_volume_profile(n_steps=env.total_steps)
    done = False
    slippages = []
    participations = []

    while not done:
        if strategy == "twap":
            action = env.twap_action()
        elif strategy == "vwap":
            action = env.vwap_action(volume_profile)
        elif strategy == "ac":
            action = env.ac_action()
        elif strategy.startswith("pov"):
            # "pov10" -> constant 10% of each step's volume. Multiple rates
            # can be listed in cfg["evaluation"]["benchmarks"] simultaneously
            # (e.g. pov5, pov10, pov20) to show where the learned policy sits
            # relative to a family of fixed-rate POV algos, rather than
            # arguing about which single rate is the "fair" comparison.
            try:
                rate = float(strategy[3:]) / 100.0
            except ValueError:
                raise ValueError(f"Could not parse POV rate from '{strategy}' "
                                  f"(expected e.g. 'pov10' for 10%)")
            action = env.pov_action(rate)
        else:
            raise ValueError(f"Unknown: {strategy}")

        obs, _, done, _, info = env.step(action)
        slippages.append(info.get("slippage_bps", 0))
        participations.append(info.get("participation_rate", 0))

    return {
        "strategy": strategy,
        "side": side,
        "ticker": getattr(env, "ticker", None),
        "total_cost_dollars": env.total_cost,
        "is_bps": env.total_cost / (env.total_shares * env.arrival_price + 1e-9) * 10_000,
        "avg_slippage_bps": float(np.mean(slippages)),
        "avg_participation_rate": float(np.mean(participations)),
        "unfilled_fraction": env.remaining / env.total_shares,
    }


def run_rl_episode(env, predict_fn, side: str, urgency: float = 0.5) -> dict:
    env.default_side = side
    env.default_urgency = urgency
    obs, _ = env.reset()
    done = False
    slippages, participations = [], []
    while not done:
        action = predict_fn(obs)
        obs, _, done, _, info = env.step(action)
        slippages.append(info.get("slippage_bps", 0))
        participations.append(info.get("participation_rate", 0))
    return {
        "strategy": "rl_fast",
        "side": side,
        "ticker": getattr(env, "ticker", None),
        "total_cost_dollars": env.total_cost,
        "is_bps": env.total_cost / (env.total_shares * env.arrival_price + 1e-9) * 10_000,
        "avg_slippage_bps": float(np.mean(slippages)),
        "avg_participation_rate": float(np.mean(participations)),
        "unfilled_fraction": env.remaining / env.total_shares,
    }


def run_backtest(cfg, model_path, n_episodes, seed=99999):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Load model — supports both SB3 zip and raw .pt
    print(f"Loading model from {model_path}...")
    # Strip .pt extension if passed — SB3 uses .zip
    load_path = model_path.replace("_best.pt", "").replace(".pt", "")
    model_sb3 = PPO.load(load_path, device="cpu")
    def predict_fn(obs):
        action, _ = model_sb3.predict(obs, deterministic=True)
        return action
    print("Model loaded.")

    # Use the standard Gymnasium env for evaluation (single episodes)
    # IMPORTANT: evaluate on the held-out test split, not the full dataset —
    # otherwise this backtest is scoring the model on days it trained on.
    data_cfg = cfg["data"]
    exec_cfg = cfg["execution"]
    if data_cfg["source"] == "csv":
        full_df = load_csv_data(data_cfg["path"], exec_cfg["step_duration_min"])
    else:
        full_df = generate_intraday_data(SyntheticMarketConfig(
            avg_daily_volume=cfg["market"]["avg_daily_volume"],
            steps_per_day=exec_cfg["total_steps"],
            volatility_per_min=cfg["market"]["volatility_per_min"],
            avg_spread_bps=cfg["market"]["avg_spread_bps"],
            step_duration_min=exec_cfg["step_duration_min"],
        ))
    test_frac = data_cfg.get("test_frac", 0.2)
    _, test_df = train_test_split_days(full_df, test_frac=test_frac)

    env = ExecutionEnv(cfg, data=test_df, side="buy")

    # Seed the episode-sampling RNG once at the start of the run so that
    # which days/tickers get sampled (and all downstream market randomness)
    # is fully reproducible given the same seed. Without this, self.rng in
    # ExecutionEnv is unseeded (np.random.default_rng() with no argument),
    # so every call to run_backtest samples a different random subset of
    # episodes and the reported improvement % swings run-to-run even
    # against the exact same model and data.
    env.reset(seed=seed)

    strategies = cfg["evaluation"]["benchmarks"]
    sides = ["buy", "sell"]
    results = []

    for side in sides:
        # Benchmarks
        for strategy in strategies:
            desc = f"{strategy.upper()} ({side})"
            for ep in tqdm(range(n_episodes), desc=desc):
                row = run_benchmark_episode(env, strategy, side)
                row["episode"] = ep
                results.append(row)

        # RL agent
        desc = f"RL_FAST ({side})"
        for ep in tqdm(range(n_episodes), desc=desc):
            row = run_rl_episode(env, predict_fn, side)
            row["episode"] = ep
            results.append(row)

    return pd.DataFrame(results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config",     default="configs/default.yaml")
    parser.add_argument("--model-path", default="models/fast_model_best.pt")
    parser.add_argument("--n-episodes", type=int, default=None)
    parser.add_argument("--output",     default="evaluation/results_fast.csv")
    parser.add_argument("--seed",       type=int, default=99999)
    args = parser.parse_args()

    cfg = load_config(args.config)
    n_episodes = args.n_episodes or cfg["evaluation"]["n_episodes"]

    df = run_backtest(cfg, args.model_path, n_episodes, seed=args.seed)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"\nResults saved to {args.output}")

    print("\n=== Summary ===")
    summary = df.groupby(["strategy", "side"])["is_bps"].agg(["mean", "std"]).round(2)
    print(summary.to_string())

    # Compare RL vs each benchmark (twap, vwap, ac — whatever's in cfg["evaluation"]["benchmarks"])
    strategies = cfg["evaluation"]["benchmarks"]
    for side in ["buy", "sell"]:
        rl = df[(df["strategy"] == "rl_fast") & (df["side"] == side)]["is_bps"].mean()
        for strategy in strategies:
            bench = df[(df["strategy"] == strategy) & (df["side"] == side)]["is_bps"].mean()
            diff = bench - rl
            pct = diff / (abs(bench) + 1e-9) * 100
            tag = "improvement" if diff > 0 else "worse"
            print(f"  [{side.upper()}] RL vs {strategy.upper()}: {diff:+.2f} bps ({pct:+.1f}%) — {tag}")
        print()