"""
run.py — full pipeline using the LOB-based simulator throughout

Unlike run_fast.py (which trains on the fast vectorized formula-based
simulator but evaluates on the LOB-based one — a train/eval mismatch),
this script trains AND evaluates on simulator/market.py's MarketSimulator
the whole way through. Slower to train, but the number you get out the
other end reflects the same market model start to finish, which matters
for presenting this as a serious execution strategy rather than a
research prototype.

Usage:
    python run.py                        # train + backtest + TCA
    python run.py --timesteps 2000000   # shorter training run
    python run.py --skip-train          # backtest only (uses existing model)
"""

import argparse
import yaml
from pathlib import Path


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config",     default="configs/default.yaml")
    parser.add_argument("--skip-train", action="store_true")
    parser.add_argument("--timesteps",  type=int, default=None)
    parser.add_argument("--n-episodes", type=int, default=None)
    parser.add_argument("--model-path", default="models/best_model.zip")
    parser.add_argument("--results",    default="evaluation/results.csv")
    parser.add_argument("--plot-dir",   default="evaluation/plots")
    parser.add_argument("--seed",       type=int, default=99999)
    parser.add_argument("--train-seed", type=int, default=None,
                         help="Override training.seed from config. Distinct from --seed, "
                              "which controls BACKTEST episode sampling. Used for the "
                              "training-seed variance study.")
    args = parser.parse_args()

    cfg = load_config(args.config)

    # ----------------------------------------------------------------
    # 1. Train (LOB-based simulator, via agent/env.py + agent/train.py)
    # ----------------------------------------------------------------
    if not args.skip_train:
        print("=" * 60)
        print("PHASE 1: Training (LOB-based simulator)")
        print("=" * 60)
        from agent.train import train
        timesteps = args.timesteps or cfg["training"]["total_timesteps"]
        if args.train_seed is not None:
            cfg["training"]["seed"] = args.train_seed
            print(f"Overriding training seed -> {args.train_seed}")
        train(cfg, total_timesteps=timesteps)
    else:
        print("Skipping training.")

    # ----------------------------------------------------------------
    # 2. Backtest — already uses the same LOB simulator via ExecutionEnv,
    #    and already evaluates on the held-out test split
    # ----------------------------------------------------------------
    print("\n" + "=" * 60)
    print("PHASE 2: Backtest")
    print("=" * 60)
    from evaluation.backtest_fast import run_backtest
    n_episodes = args.n_episodes or cfg["evaluation"]["n_episodes"]
    df = run_backtest(cfg, args.model_path, n_episodes, seed=args.seed)
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
    df["strategy"] = df["strategy"].replace("rl_fast", "rl")
    df.to_csv(args.results, index=False)
    run_tca(args.results, args.plot_dir)

    print("\n" + "=" * 60)
    print("Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()