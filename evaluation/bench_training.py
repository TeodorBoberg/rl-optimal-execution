"""
evaluation/bench_training.py

Finds where training wall-clock actually goes, given that raw environment
stepping was measured at ~2,210 steps/sec/process while actual training
achieves ~45 steps/sec/env -- a ~49x gap that is NOT the simulator.

Two suspects, with different fixes:

  SubprocVecEnv IPC. Every step pickles observations and actions across
  process boundaries. With a 13-float observation and a fast environment,
  serialisation can cost more than the simulation itself. DummyVecEnv
  (single process, sequential) frequently wins outright below a crossover
  point in env speed, and 2,210 steps/sec is well below it.

  PPO update cost. With n_steps=512, n_epochs=10, every 512*n_envs
  collected steps triggers 10 passes over the buffer. On GPU, per-minibatch
  transfer overhead can dominate, which is why SB3 warns that MlpPolicy
  is usually faster on CPU.

This runs short trainings across combinations of vec env type, n_envs and
device, and reports the fps SB3 itself measures.

Usage:
    python evaluation/bench_training.py --timesteps 30000
"""

import sys
import os
import argparse
import time
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
os.chdir(_root)

import numpy as np
import yaml

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

from agent.env import ExecutionEnv
from simulator.synthetic_data import load_csv_data
from simulator.data_split import train_test_split_days


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def make_env_fn(cfg, data, seed, side="random"):
    def _init():
        env = ExecutionEnv(cfg, data=data, side=side)
        env.reset(seed=seed)
        return env
    return _init


def bench(cfg, train_df, vec_cls, n_envs, device, timesteps, tcfg):
    fns = [make_env_fn(cfg, train_df, 1000 + i) for i in range(n_envs)]
    venv = vec_cls(fns)
    try:
        model = PPO(
            "MlpPolicy", venv, device=device, verbose=0,
            n_steps=tcfg.get("n_steps", 512),
            batch_size=tcfg.get("batch_size", 512),
            n_epochs=tcfg.get("n_epochs", 10),
            learning_rate=tcfg.get("learning_rate", 1e-4),
            gamma=tcfg.get("gamma", 0.998),
            policy_kwargs=dict(net_arch=[256, 256]),
        )
        t0 = time.perf_counter()
        model.learn(total_timesteps=timesteps, progress_bar=False)
        dt = time.perf_counter() - t0
        return timesteps / dt, dt
    finally:
        venv.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--timesteps", type=int, default=30000)
    args = parser.parse_args()

    cfg = load_config(args.config)
    d, e = cfg["data"], cfg["execution"]
    tcfg = cfg.get("training", {})
    full = load_csv_data(d["path"], e["step_duration_min"])
    train_df, _ = train_test_split_days(full, test_frac=d.get("test_frac", 0.2))

    import torch
    devices = ["cpu"] + (["cuda"] if torch.cuda.is_available() else [])
    print(f"Devices available: {devices}")
    print(f"CPU cores: {os.cpu_count()}")
    print(f"Baseline from config: n_envs={tcfg.get('n_envs')}, "
          f"n_steps={tcfg.get('n_steps')}, batch_size={tcfg.get('batch_size')}, "
          f"n_epochs={tcfg.get('n_epochs')}")
    print(f"\nEach run trains {args.timesteps:,} timesteps.\n")

    combos = [
        ("SubprocVecEnv", SubprocVecEnv, 8),
        ("DummyVecEnv", DummyVecEnv, 8),
        ("DummyVecEnv", DummyVecEnv, 16),
        ("SubprocVecEnv", SubprocVecEnv, 16),
    ]

    print(f"{'vec env':>16} | {'n_envs':>6} | {'device':>6} | {'fps':>9} | {'seconds':>8}")
    results = []
    for name, cls, n in combos:
        for dev in devices:
            try:
                fps, dt = bench(cfg, train_df, cls, n, dev, args.timesteps, tcfg)
                results.append((name, n, dev, fps))
                print(f"{name:>16} | {n:>6} | {dev:>6} | {fps:>9,.0f} | {dt:>8.1f}")
            except Exception as ex:
                print(f"{name:>16} | {n:>6} | {dev:>6} |    FAILED  ({type(ex).__name__}: {ex})")

    if results:
        best = max(results, key=lambda r: r[3])
        base = next((r for r in results if r[0] == "SubprocVecEnv"
                     and r[1] == 8 and r[2] == "cuda"), None)
        print(f"\nFastest: {best[0]}, n_envs={best[1]}, device={best[2]} "
              f"-> {best[3]:,.0f} fps")
        if base:
            print(f"Current setup (SubprocVecEnv, 8 envs, cuda): {base[3]:,.0f} fps")
            print(f"Speedup available: {best[3]/base[3]:.1f}x "
                  f"-> an 8h run becomes ~{8/(best[3]/base[3]):.1f}h")

    print("\nIf DummyVecEnv beats SubprocVecEnv, IPC was the bottleneck.")
    print("If cpu beats cuda, transfer overhead was dominating the tiny MLP.")
    print("If neither helps much, the PPO update itself dominates -- reduce")
    print("n_epochs (10 is high) or raise n_steps to update less often.")


if __name__ == "__main__":
    main()