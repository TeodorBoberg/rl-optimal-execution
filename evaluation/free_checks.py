"""
evaluation/free_checks.py

Two checks that need no training, only an existing model and the tick data
already purchased.

1. STOCHASTIC POLICY EVALUATION
   Every result so far used deterministic=True, taking the mean of the
   policy's action distribution. PPO learns a distribution, and at
   deployment you could sample from it instead. If sampled performance is
   far worse, the policy is relying on a narrow action range and is more
   fragile than the deterministic numbers suggest. If it is similar, the
   policy is robust to its own exploration noise.

2. OBSERVED PARTICIPATION RATES
   max_participation_rate is set to 0.25 and has never been justified from
   data -- it is one of the hand-chosen thresholds that shapes every
   result, because it caps how fast any strategy can trade. This measures
   what participation rates real individual trades actually reach, which
   at least bounds the assumption.

Usage:
    python evaluation/free_checks.py --model-path models/best_model.zip
    python evaluation/free_checks.py --model-path models/best_model.zip --skip-participation
"""

import argparse
import glob
import os
import sys
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
os.chdir(_root)

import numpy as np
import pandas as pd
import yaml


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def stochastic_check(args):
    from stable_baselines3 import PPO
    from agent.env import ExecutionEnv
    from simulator.synthetic_data import load_csv_data, load_empirical_volume_profile
    from simulator.data_split import train_test_split_days

    cfg = load_config(args.config)
    d, e = cfg["data"], cfg["execution"]
    full = load_csv_data(d["path"], e["step_duration_min"])
    _, test_df = train_test_split_days(full, test_frac=d.get("test_frac", 0.2))

    model = PPO.load(args.model_path.replace(".zip", ""), device="cpu")
    strategies = cfg["evaluation"]["benchmarks"]

    print("=" * 70)
    print("1. DETERMINISTIC vs STOCHASTIC POLICY")
    print("=" * 70)
    print(f"{args.n_episodes} episodes per setting, same seed, same data.\n")

    out = {}
    for det in [True, False]:
        costs = {"rl": [], **{s: [] for s in strategies}}
        for side in ["buy", "sell"]:
            env = ExecutionEnv(cfg, data=test_df, side=side)
            env.reset(seed=args.seed)
            profile = load_empirical_volume_profile(n_steps=env.total_steps)

            for _ in range(args.n_episodes):
                obs, _ = env.reset()
                done = False
                while not done:
                    a, _ = model.predict(obs, deterministic=det)
                    obs, _, done, _, info = env.step(a)
                costs["rl"].append((side, info["is_bps"]))

            for s in strategies:
                env2 = ExecutionEnv(cfg, data=test_df, side=side)
                env2.reset(seed=args.seed)
                for _ in range(args.n_episodes):
                    obs, _ = env2.reset()
                    done = False
                    while not done:
                        if s == "twap":
                            a = env2.twap_action()
                        elif s == "vwap":
                            a = env2.vwap_action(profile)
                        elif s == "ac":
                            a = env2.ac_action()
                        elif s.startswith("pov"):
                            a = env2.pov_action(float(s[3:]) / 100.0)
                        else:
                            continue
                        obs, _, done, _, info = env2.step(a)
                    costs[s].append((side, info["is_bps"]))
        out["deterministic" if det else "stochastic"] = costs

    label = {True: "deterministic", False: "stochastic"}
    print(f"{'':>22} | {'deterministic':>14} | {'stochastic':>11} | {'change':>8}")
    for side in ["buy", "sell"]:
        for name in ["rl"] + strategies:
            dv = np.mean([c for s, c in out["deterministic"][name] if s == side])
            sv = np.mean([c for s, c in out["stochastic"][name] if s == side])
            if name != "rl":
                continue
            print(f"{'RL cost (' + side + ', bps)':>22} | {dv:>14.2f} | {sv:>11.2f} | "
                  f"{(sv - dv) / max(dv, 1e-9) * 100:>+7.1f}%")

    print()
    for side in ["buy", "sell"]:
        for s in strategies:
            d_rl = np.mean([c for sd, c in out["deterministic"]["rl"] if sd == side])
            s_rl = np.mean([c for sd, c in out["stochastic"]["rl"] if sd == side])
            d_b = np.mean([c for sd, c in out["deterministic"][s] if sd == side])
            s_b = np.mean([c for sd, c in out["stochastic"][s] if sd == side])
            di = (d_b - d_rl) / (abs(d_b) + 1e-9) * 100
            si = (s_b - s_rl) / (abs(s_b) + 1e-9) * 100
            print(f"  [{side.upper()}] vs {s.upper():6s}: deterministic {di:+6.1f}%   "
                  f"stochastic {si:+6.1f}%   ({si - di:+.1f} pts)")

    print("\nA large drop under sampling means the policy depends on a narrow action")
    print("range and is more fragile than the deterministic numbers imply.\n")


def participation_check(args):
    from evaluation.lee_ready import classify_trades

    print("=" * 70)
    print("2. OBSERVED PARTICIPATION RATES IN REAL DATA")
    print("=" * 70)

    files = sorted(glob.glob(os.path.join(args.tick_dir, "*_tbbo_*.csv")))
    files = [f for f in files if "_classified" not in os.path.basename(f)]
    if not files:
        print(f"No tick files in {args.tick_dir} -- skipping.\n")
        return

    by_ticker = {}
    for f in files:
        by_ticker.setdefault(os.path.basename(f).split("_tbbo_")[0], []).append(f)
    picked = [sorted(v)[0] for v in by_ticker.values()][:args.max_files]
    print(f"Sampling {len(picked)} file(s), up to {args.max_trades:,} trades each\n")

    rows = []
    for path in picked:
        try:
            df = pd.read_csv(path, usecols=["ts_event", "price", "size",
                                             "bid_px_00", "ask_px_00"])
        except ValueError:
            continue
        ts = pd.to_datetime(df["ts_event"], errors="coerce", utc=True)
        if ts.isna().all():
            ts = pd.to_datetime(df["ts_event"], unit="ns", errors="coerce", utc=True)
        df["ts_event"] = ts
        df = df.dropna(subset=["ts_event"]).sort_values("ts_event")
        east = df["ts_event"].dt.tz_convert("US/Eastern")
        df = df[(east.dt.time >= pd.Timestamp("09:30").time()) &
                (east.dt.time < pd.Timestamp("16:00").time())].copy()
        if df.empty:
            continue
        if args.max_trades and len(df) > args.max_trades:
            df = df.iloc[:args.max_trades]
        df["minute"] = df["ts_event"].dt.tz_convert("US/Eastern").dt.floor("1min")
        per_min = df.groupby("minute")["size"].agg(["sum", "max"])
        per_min = per_min[per_min["sum"] > 0]
        rows.append(pd.DataFrame({
            "ticker": os.path.basename(path).split("_tbbo_")[0],
            "largest_trade_share": per_min["max"] / per_min["sum"],
        }))

    if not rows:
        print("No usable data.\n")
        return
    r = pd.concat(rows, ignore_index=True)

    print("Largest single trade as a share of that minute's total volume:")
    print(r["largest_trade_share"].describe(
        percentiles=[0.5, 0.9, 0.95, 0.99]).round(4).to_string())
    for t in [0.10, 0.25, 0.50]:
        print(f"  minutes where one trade took >{t:.0%} of volume: "
              f"{(r['largest_trade_share'] > t).mean():.2%}")
    print(f"\nConfigured max_participation_rate: 0.25")
    print("This bounds the assumption rather than deriving it: a single trade")
    print("taking a quarter of a minute's volume is common, so a cap at 0.25 is")
    print("not obviously wrong -- but a parent order is not a single trade, and")
    print("this cannot tell you what an execution algorithm should be allowed.\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--model-path", default="models/best_model.zip")
    parser.add_argument("--n-episodes", type=int, default=150)
    parser.add_argument("--seed", type=int, default=99999)
    parser.add_argument("--tick-dir", default="data/tick")
    parser.add_argument("--max-files", type=int, default=13)
    parser.add_argument("--max-trades", type=int, default=300000)
    parser.add_argument("--skip-stochastic", action="store_true")
    parser.add_argument("--skip-participation", action="store_true")
    args = parser.parse_args()

    if not args.skip_stochastic:
        stochastic_check(args)
    if not args.skip_participation:
        participation_check(args)


if __name__ == "__main__":
    main()