"""
evaluation/trace_ticker.py

Runs and logs per-step trade traces for a single ticker/side/strategy, to
diagnose *why* the RL policy loses to benchmarks on certain names (e.g.
GOOGL sells lost badly to TWAP) while winning clearly on others (e.g. MSFT).

The regular backtest functions in backtest_fast.py only return each
episode's final aggregated cost -- the step-by-step trade path is
discarded. This script keeps it, so you can compare *how* the policy
trades a losing ticker vs a winning one (front-loaded? back-loaded?
smooth? does it hit the drawdown stop? does it hit the position cap?).

Usage:
    python evaluation/trace_ticker.py --ticker GOOGL --side sell --strategy rl --n-episodes 10
    python evaluation/trace_ticker.py --ticker GOOGL --side sell --strategy twap --n-episodes 10
    python evaluation/trace_ticker.py --ticker MSFT  --side sell --strategy rl --n-episodes 10
"""

import argparse
import sys
import os
import yaml
import numpy as np
import pandas as pd
from pathlib import Path

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
os.chdir(_root)

import torch
from stable_baselines3 import PPO
from agent.env import ExecutionEnv
from simulator.synthetic_data import u_shaped_volume_profile, load_empirical_volume_profile, load_csv_data
from simulator.data_split import train_test_split_days


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def run_traced_episode(env, strategy, side, predict_fn=None, urgency=0.5):
    env.default_side = side
    if strategy == "rl":
        env.default_urgency = urgency
    obs, _ = env.reset()
    ticker = getattr(env, "ticker", None)
    volume_profile = load_empirical_volume_profile(n_steps=env.total_steps)
    done = False
    rows = []
    step = 0
    while not done:
        pre_remaining = env.remaining
        state_before = env.sim.current_state
        mid_before = state_before["mid_price"]
        regime_before = state_before["regime"]

        if strategy == "rl":
            action = predict_fn(obs)
        elif strategy == "twap":
            action = env.twap_action()
        elif strategy == "vwap":
            action = env.vwap_action(volume_profile)
        elif strategy == "ac":
            action = env.ac_action()
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

        obs, reward, done, _, info = env.step(action)
        qty_traded = pre_remaining - info["remaining"]

        rows.append({
            "step": step,
            "ticker": ticker,
            "mid_price_before": mid_before,
            "regime": regime_before,
            "remaining_before": pre_remaining,
            "remaining_after": info["remaining"],
            "qty_traded": qty_traded,
            "qty_traded_frac_of_total": qty_traded / env.total_shares,
            "step_cost": info["step_cost"],
            "cumulative_cost": info["total_cost"],
            "slippage_bps": info["slippage_bps"],
            "participation_rate": info["participation_rate"],
            "drawdown_stop": info["drawdown_stop"],
            "hit_position_limit": info["hit_position_limit"],
        })
        step += 1

    final_is_bps = env.total_cost / (env.total_shares * env.arrival_price + 1e-9) * 10_000
    return pd.DataFrame(rows), final_is_bps, ticker


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config",      default="configs/default.yaml")
    parser.add_argument("--model-path",  default="models/best_model.zip")
    parser.add_argument("--ticker",      required=True)
    parser.add_argument("--side",        default="sell", choices=["buy", "sell"])
    parser.add_argument("--strategy",    default="rl", choices=["rl", "twap", "vwap", "ac"])
    parser.add_argument("--n-episodes",  type=int, default=10)
    parser.add_argument("--urgency",     type=float, default=0.5,
                         help="Urgency level to test (0.0=patient, 0.5=normal, 1.0=urgent). Only affects --strategy rl.")
    parser.add_argument("--seed",        type=int, default=99999)
    parser.add_argument("--output-dir",  default="evaluation/traces")
    args = parser.parse_args()

    cfg = load_config(args.config)
    data_cfg = cfg["data"]
    exec_cfg = cfg["execution"]

    if data_cfg["source"] != "csv":
        raise SystemExit("trace_ticker.py requires CSV data with a ticker column.")

    full_df = load_csv_data(data_cfg["path"], exec_cfg["step_duration_min"])
    if "ticker" not in full_df.columns:
        raise SystemExit("Loaded data has no 'ticker' column -- can't isolate a single ticker.")

    test_frac = data_cfg.get("test_frac", 0.2)
    _, test_df = train_test_split_days(full_df, test_frac=test_frac)

    ticker_df = test_df[test_df["ticker"].str.lower() == args.ticker.lower()].copy()
    if ticker_df.empty:
        available = sorted(test_df["ticker"].unique().tolist())
        raise SystemExit(f"No rows for ticker '{args.ticker}' in test split. Available: {available}")

    # IMPORTANT: day IDs in the combined dataset are unique across the whole
    # multi-ticker file (see synthetic_data.py's combine-safety comment), so
    # after filtering to one ticker they won't be a contiguous 0..n_days-1
    # range. ExecutionEnv.reset() samples day_idx via rng.integers(0, n_days)
    # and looks it up with get_day(df, day_idx) -- an exact match on the
    # 'day' value, not a positional index. Without remapping, every reset()
    # would sample a day_idx that doesn't exist in this ticker's subset and
    # get_day() would silently return an empty frame. Remap to a local,
    # contiguous 0-indexed range so sampling works correctly.
    unique_days = sorted(ticker_df["day"].unique())
    day_map = {old: new for new, old in enumerate(unique_days)}
    ticker_df["day"] = ticker_df["day"].map(day_map)

    print(f"Isolated {len(unique_days)} test day(s) for {args.ticker.upper()}")

    env = ExecutionEnv(cfg, data=ticker_df, side=args.side)
    env.reset(seed=args.seed)  # reproducible day sampling within this ticker's days

    predict_fn = None
    if args.strategy == "rl":
        print(f"Loading model from {args.model_path}...")
        load_path = args.model_path.replace("_best.pt", "").replace(".pt", "")
        model_sb3 = PPO.load(load_path)

        def predict_fn(obs):
            action, _ = model_sb3.predict(obs, deterministic=True)
            return action

        print("Model loaded.")

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    all_traces = []
    summaries = []
    for ep in range(args.n_episodes):
        trace_df, is_bps, ticker = run_traced_episode(env, args.strategy, args.side, predict_fn, urgency=args.urgency)
        trace_df["episode"] = ep
        all_traces.append(trace_df)
        summaries.append({"episode": ep, "ticker": ticker, "is_bps": is_bps})
        print(f"  Episode {ep}: ticker={ticker}, final is_bps={is_bps:.2f}")

    full_trace = pd.concat(all_traces, ignore_index=True)
    out_path = Path(args.output_dir) / f"trace_{args.ticker.lower()}_{args.side}_{args.strategy}_urgency{args.urgency:.2f}.csv"
    full_trace.to_csv(out_path, index=False)
    print(f"\nFull step-by-step trace saved to {out_path}")

    summary_df = pd.DataFrame(summaries)
    print("\n=== Summary ===")
    print(summary_df.to_string())
    print(f"\nMean is_bps: {summary_df['is_bps'].mean():.2f}, std: {summary_df['is_bps'].std():.2f}")
    print(f"Episodes hitting drawdown stop: {full_trace.groupby('episode')['drawdown_stop'].any().sum()}/{args.n_episodes}")
    print(f"Episodes hitting position cap at least once: {full_trace.groupby('episode')['hit_position_limit'].any().sum()}/{args.n_episodes}")

    # Trade shape: fraction of total shares traded per third of the episode
    full_trace["time_bucket"] = pd.cut(full_trace["step"], bins=3, labels=["early", "mid", "late"])
    shape = full_trace.groupby("time_bucket", observed=True)["qty_traded_frac_of_total"].sum()
    print("\n=== Trade shape (fraction of total shares traded per third of episode, summed across all episodes) ===")
    print(shape.to_string())


if __name__ == "__main__":
    main()