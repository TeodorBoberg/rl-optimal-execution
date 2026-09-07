"""
evaluation/profile_speed.py

Measures where training time actually goes, before changing anything.

Three things are timed separately:
  1. Raw environment stepping, no RL involved
  2. Policy forward pass (action selection) on CPU vs GPU
  3. The two combined, as PPO's rollout phase does it

The point is to establish whether the bottleneck is the ENVIRONMENT
(Python/pandas/numpy overhead) or the NETWORK (matrix multiplies). These
have completely different fixes: a slow environment is fixed by removing
Python overhead or vectorising, a slow network by using the GPU. Guessing
wrong wastes days.

SB3 already warns that PPO with an MlpPolicy is usually FASTER on CPU than
GPU, because a [256,256] network's compute is trivial next to the
per-step CPU-GPU transfer overhead. This measures whether that holds here.

Usage:
    python evaluation/profile_speed.py --config configs/default.yaml
"""

import sys
import os
import argparse
import time
import cProfile
import pstats
import io
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
os.chdir(_root)

import numpy as np
import yaml

from agent.env import ExecutionEnv
from simulator.synthetic_data import load_csv_data
from simulator.data_split import train_test_split_days


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--n-steps", type=int, default=5000)
    parser.add_argument("--top", type=int, default=25)
    args = parser.parse_args()

    cfg = load_config(args.config)
    d, e = cfg["data"], cfg["execution"]
    full = load_csv_data(d["path"], e["step_duration_min"])
    train_df, _ = train_test_split_days(full, test_frac=d.get("test_frac", 0.2))

    env = ExecutionEnv(cfg, data=train_df, side="sell")
    obs, _ = env.reset(seed=1)
    adim = env.action_space.shape[0]
    act = np.full(adim, 0.3, dtype=np.float32)

    # ---- 1. Raw environment stepping ----
    print(f"Timing {args.n_steps:,} raw env.step() calls (no RL)...")
    t0 = time.perf_counter()
    n = 0
    while n < args.n_steps:
        obs, _, done, _, _ = env.step(act)
        n += 1
        if done:
            obs, _ = env.reset()
    t_env = time.perf_counter() - t0
    env_fps = args.n_steps / t_env
    print(f"  {t_env:.2f}s  ->  {env_fps:,.0f} env steps/sec/process")
    print(f"  {t_env/args.n_steps*1e6:,.0f} microseconds per step")

    # ---- 2. Policy forward pass, CPU vs GPU ----
    try:
        import torch
        from stable_baselines3 import PPO
        print("\nTiming policy forward pass (action selection):")
        for device in (["cpu", "cuda"] if torch.cuda.is_available() else ["cpu"]):
            m = PPO("MlpPolicy", env, device=device, verbose=0,
                     policy_kwargs=dict(net_arch=[256, 256]))
            o = obs.reshape(1, -1)
            for _ in range(50):
                m.predict(o, deterministic=True)
            t0 = time.perf_counter()
            for _ in range(2000):
                m.predict(o, deterministic=True)
            dt = time.perf_counter() - t0
            print(f"  {device:>4}: {dt/2000*1e6:7.0f} us/call  "
                  f"({2000/dt:,.0f} calls/sec)")
        if torch.cuda.is_available():
            print(f"  GPU: {torch.cuda.get_device_name(0)}")
        else:
            print("  CUDA not available to torch -- training is CPU-only.")
    except Exception as ex:
        print(f"  Could not time policy: {ex}")

    # ---- 3. Where the env time goes ----
    print(f"\nProfiling env.step() internals ({args.top} slowest by cumulative time):")
    env2 = ExecutionEnv(cfg, data=train_df, side="sell")
    env2.reset(seed=1)

    def run():
        k = 0
        while k < 3000:
            _, _, dn, _, _ = env2.step(act)
            k += 1
            if dn:
                env2.reset()

    pr = cProfile.Profile()
    pr.enable()
    run()
    pr.disable()
    s = io.StringIO()
    pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(args.top)
    for line in s.getvalue().splitlines():
        if line.strip():
            print("  " + line)

    print("\n" + "=" * 68)
    print("HOW TO READ THIS")
    print("=" * 68)
    print(f"Observed training throughput was ~359 fps with 8 parallel envs,")
    print(f"i.e. ~45 steps/sec/env. Raw single-process env stepping here is")
    print(f"{env_fps:,.0f} steps/sec.")
    print()
    print("If raw env stepping is MUCH faster than 45/sec, the loss is in")
    print("SubprocVecEnv inter-process overhead or the PPO update, not the env.")
    print("If it is close to 45/sec, the environment itself is the bottleneck")
    print("and the profile above shows exactly which calls to attack.")
    print()
    print("Look for pandas .loc / __getitem__ high in the list: returning a")
    print("Series costs 50-150us per call and there are several per step.")


if __name__ == "__main__":
    main()