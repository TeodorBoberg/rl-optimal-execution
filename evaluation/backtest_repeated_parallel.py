"""
evaluation/backtest_repeated_parallel.py

Parallel version of backtest_repeated.py. Runs each evaluation seed in its
own process, since the seeds are independent by construction.

Why this matters: run_backtest is single-process, so a 5-run x 1000-episode
x 7-strategy x 2-side backtest is ~70,000 episodes (~27M environment steps)
executed on ONE core while the rest of the machine idles. At the measured
~2,145 env steps/sec that is ~3.5 hours. Training already uses 16 workers;
evaluation used one.

Results are identical to the serial version: each worker calls the same
run_backtest with the same seed, and seeds were already independent, so
parallelising changes scheduling only, not numbers.

MEMORY: each worker loads the model and its own copy of the bar data. With
the 2.4M-row dataset expect roughly 1-2GB per worker, so keep
--n-workers below (free RAM in GB) / 2.

Usage:
    python evaluation/backtest_repeated_parallel.py --config configs/default.yaml \
        --model-path models/best_model.zip --n-runs 5 --n-episodes 1000
    python evaluation/backtest_repeated_parallel.py ... --n-workers 5
"""

import argparse
import sys
import os
import yaml
import numpy as np
import pandas as pd
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
os.chdir(_root)


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def _run_one(payload):
    """
    Worker entry point. Imports happen INSIDE the worker so the parent does
    not need heavy modules loaded before forking, and so this works under
    Windows spawn semantics (where the child re-imports rather than
    inheriting parent memory).
    """
    import os as _os
    import sys as _sys
    _root_ = payload["root"]
    if _root_ not in _sys.path:
        _sys.path.insert(0, _root_)
    _os.chdir(_root_)

    from evaluation.backtest_fast import run_backtest

    cfg = payload["cfg"]
    df = run_backtest(cfg, payload["model_path"], payload["n_episodes"],
                       seed=payload["seed"])
    rl_label = "rl" if "rl" in df["strategy"].unique() else "rl_fast"

    out = {"seed": payload["seed"]}
    for side in ["buy", "sell"]:
        rl = df[(df["strategy"] == rl_label) & (df["side"] == side)]["is_bps"].mean()
        for s in payload["strategies"]:
            bench = df[(df["strategy"] == s) & (df["side"] == side)]["is_bps"].mean()
            out[f"{side}|{s}"] = (bench - rl) / (abs(bench) + 1e-9) * 100
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--model-path", default="models/best_model.zip")
    parser.add_argument("--n-episodes", type=int, default=None)
    parser.add_argument("--n-runs", type=int, default=5)
    parser.add_argument("--base-seed", type=int, default=99999)
    parser.add_argument("--n-workers", type=int, default=None,
                         help="Default: min(n_runs, cpu_count-1). Each worker uses "
                              "~1-2GB with the full dataset.")
    parser.add_argument("--output", default="evaluation/results_repeated_summary.csv")
    args = parser.parse_args()

    cfg = load_config(args.config)
    n_episodes = args.n_episodes or cfg["evaluation"]["n_episodes"]
    strategies = cfg["evaluation"]["benchmarks"]

    n_workers = args.n_workers or min(args.n_runs, max(1, (os.cpu_count() or 2) - 1))
    print(f"Running {args.n_runs} seeds x {n_episodes:,} episodes "
          f"across {n_workers} worker process(es)")
    print(f"Model: {args.model_path}")
    print(f"Benchmarks: {strategies}\n")

    payloads = [{
        "root": _root, "cfg": cfg, "model_path": args.model_path,
        "n_episodes": n_episodes, "strategies": strategies,
        "seed": args.base_seed + i,
    } for i in range(args.n_runs)]

    rows = []
    with ProcessPoolExecutor(max_workers=n_workers) as ex:
        futures = {ex.submit(_run_one, p): p["seed"] for p in payloads}
        done = 0
        for fut in as_completed(futures):
            seed = futures[fut]
            try:
                res = fut.result()
            except Exception as e:
                print(f"  seed {seed} FAILED: {type(e).__name__}: {e}")
                continue
            rows.append(res)
            done += 1
            print(f"  [{done}/{args.n_runs}] seed {seed} complete")
            for side in ["buy", "sell"]:
                parts = "  ".join(f"{s.upper()}:{res[f'{side}|{s}']:+.1f}%"
                                   for s in strategies)
                print(f"      {side.upper():>4}  {parts}")

    if not rows:
        raise SystemExit("All runs failed.")

    runs_df = pd.DataFrame(rows).sort_values("seed").reset_index(drop=True)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    runs_df.to_csv(args.output, index=False)

    print("\n" + "=" * 60)
    print(f"SUMMARY across {len(runs_df)} runs "
          f"(seeds {runs_df['seed'].min()}..{runs_df['seed'].max()})")
    print("=" * 60)
    any_flip = False
    for side in ["buy", "sell"]:
        for s in strategies:
            vals = runs_df[f"{side}|{s}"].values
            mean = vals.mean()
            std = vals.std(ddof=1) if len(vals) > 1 else 0.0
            flip = (vals.min() < 0) and (vals.max() > 0)
            any_flip = any_flip or flip
            flag = "  <-- SIGN FLIP ACROSS RUNS" if flip else ""
            print(f"  [{side.upper()}] RL vs {s.upper()}: {mean:+.1f}% +/- {std:.1f}%  "
                  f"(range {vals.min():+.1f}% to {vals.max():+.1f}%){flag}")

    md = args.output.replace(".csv", "_table.md")
    with open(md, "w") as f:
        f.write(f"# Backtest results across {len(runs_df)} runs "
                f"({n_episodes} episodes/run)\n\n")
        f.write("| Side | vs Benchmark | Mean Improvement | Std Dev | Range |\n")
        f.write("|---|---|---|---|---|\n")
        for side in ["buy", "sell"]:
            for s in strategies:
                vals = runs_df[f"{side}|{s}"].values
                std = vals.std(ddof=1) if len(vals) > 1 else 0.0
                f.write(f"| {side.upper()} | {s.upper()} | {vals.mean():+.1f}% | "
                        f"±{std:.1f}% | {vals.min():+.1f}% to {vals.max():+.1f}% |\n")

    print(f"\nPer-run results saved to {args.output}")
    print(f"Presentation-ready table saved to {md}")
    if any_flip:
        print("\nWARNING: at least one comparison flipped sign across seeds. "
              "Do not present that comparison as a reliable win.")
    else:
        print("\nNo sign flips across runs -- all comparisons directionally consistent.")


if __name__ == "__main__":
    main()