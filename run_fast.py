"""
run_fast.py — full pipeline using the vectorized simulator

Usage:
    python run_fast.py                        # train + backtest + TCA
    python run_fast.py --timesteps 10000000   # longer training
    python run_fast.py --skip-train           # backtest only

Why faster:
  - VecMarketSimulator runs 256 environments simultaneously in NumPy
  - All environments share one state matrix — no Python loops
  - PPO updates directly on GPU with preallocated tensors
  - Beta policy distribution is better suited to [0,1] action space
  - Typical throughput: 50,000-200,000 steps/sec vs ~2,000 with SB3
"""

import argparse
import sys
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config",     default="configs/default.yaml")
    parser.add_argument("--skip-train", action="store_true")
    parser.add_argument("--timesteps",  type=int, default=None)
    parser.add_argument("--n-episodes", type=int, default=None)
    parser.add_argument("--model-path", default="models/fast_model")
    parser.add_argument("--results",    default="evaluation/results_fast.csv")
    parser.add_argument("--plot-dir",   default="evaluation/plots_fast")
    args = parser.parse_args()

    cfg = load_config(args.config)

    # ----------------------------------------------------------------
    # 1. Train
    # ----------------------------------------------------------------
    if not args.skip_train:
        print("=" * 60)
        print("PHASE 1: Fast Training (vectorized PPO)")
        print("=" * 60)
        from agent.train_fast import train
        timesteps = args.timesteps or cfg["training"]["total_timesteps"]
        train(cfg, total_timesteps=timesteps, save_path="models/fast_model")
    else:
        print("Skipping training.")

    # ----------------------------------------------------------------
    # 2. Backtest
    # ----------------------------------------------------------------
    print("\n" + "=" * 60)
    print("PHASE 2: Backtest")
    print("=" * 60)
    from evaluation.backtest_fast import run_backtest
    n_episodes = args.n_episodes or cfg["evaluation"]["n_episodes"]
    df = run_backtest(cfg, args.model_path, n_episodes)
    Path(args.results).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.results, index=False)
    print(f"Results saved to {args.results}")

    # ----------------------------------------------------------------
    # 3. TCA
    # ----------------------------------------------------------------
    print("\n" + "=" * 60)
    print("PHASE 3: TCA")
    print("=" * 60)
    from evaluation.tca import run_tca
    # Rename rl_fast -> rl for TCA compatibility
    df["strategy"] = df["strategy"].replace("rl_fast", "rl")
    df.to_csv(args.results, index=False)
    run_tca(args.results, args.plot_dir)

    print("\n" + "=" * 60)
    print("Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
