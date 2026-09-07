import sys
import os
import argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import yaml

from agent.env import ExecutionEnv
from simulator.synthetic_data import u_shaped_volume_profile, load_csv_data, load_empirical_volume_profile
from simulator.data_split import train_test_split_days


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def trace_remaining_fraction(env, strategy, side, n_episodes=20, predict_fn=None):
    """Track remaining/total_shares trajectory for a fixed-schedule strategy OR the RL agent."""
    trajectories = []
    for ep in range(n_episodes):
        env.default_side = side
        obs, _ = env.reset()
        volume_profile = load_empirical_volume_profile(n_steps=env.total_steps)
        remaining_frac = [1.0]
        done = False
        step = 0
        while not done:
            if strategy == "twap":
                action = env.twap_action()
            elif strategy == "vwap":
                action = env.vwap_action(volume_profile)
            elif strategy == "ac":
                action = env.ac_action()
            elif strategy == "rl":
                action = predict_fn(obs)
            obs, _, done, _, info = env.step(action)
            remaining_frac.append(env.remaining / env.total_shares)
            step += 1
        trajectories.append(remaining_frac)
    return trajectories


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--model-path", default="models/best_model_1MIN_CALIBRATED.zip")
    parser.add_argument("--n-episodes", type=int, default=20)
    args = parser.parse_args()

    cfg = load_config(args.config)
    data_cfg = cfg["data"]
    exec_cfg = cfg["execution"]
    full_df = load_csv_data(data_cfg["path"], exec_cfg["step_duration_min"])
    test_frac = data_cfg.get("test_frac", 0.2)
    _, test_df = train_test_split_days(full_df, test_frac=test_frac)

    env = ExecutionEnv(cfg, data=test_df, side="buy")

    strategies = ["twap", "vwap", "ac"]
    predict_fn = None
    try:
        from stable_baselines3 import PPO
        print(f"Loading model from {args.model_path}...")
        model_sb3 = PPO.load(args.model_path.replace(".zip", ""))

        def predict_fn(obs):
            action, _ = model_sb3.predict(obs, deterministic=True)
            return action

        strategies.append("rl")
        print("Model loaded -- will also trace the RL agent's trajectory.")
    except Exception as e:
        print(f"Could not load model ({e}) -- skipping RL agent trace, benchmarks only.")

    for strategy in strategies:
        print(f"\n=== {strategy.upper()} remaining-fraction trajectory ({args.n_episodes} episodes) ===")
        trajs = trace_remaining_fraction(env, strategy, "sell", n_episodes=args.n_episodes,
                                          predict_fn=predict_fn)
        trajs = np.array(trajs)

        n_steps = trajs.shape[1] - 1
        checkpoints = [0.25, 0.5, 0.75, 0.9, 0.99]
        for cp in checkpoints:
            idx = int(cp * n_steps)
            expected_remaining = 1.0 - cp
            actual = trajs[:, idx]
            print(f"  At {cp:.0%} through the day: mean remaining={actual.mean():.3f} "
                  f"(perfect on-schedule would be ~{expected_remaining:.3f}), "
                  f"max remaining={actual.max():.3f}, "
                  f"episodes with >2x expected backlog: {(actual > 2*expected_remaining + 0.01).sum()}/{args.n_episodes}")

        second_to_last = trajs[:, -2]
        print(f"  Remaining just BEFORE final step: mean={second_to_last.mean():.3f}, "
              f"median={np.median(second_to_last):.3f}, max={second_to_last.max():.3f}")


if __name__ == "__main__":
    main()