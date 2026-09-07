"""
evaluation/ticker_breakdown.py

Breaks down RL-vs-benchmark performance by ticker, to identify which
names are driving variance in the aggregate numbers -- in particular,
SELL vs TWAP, which showed the widest run-to-run variance (+3.5% to
+37.7%) of the six headline comparisons.

Requires results.csv to have a 'ticker' column (added to
backtest_fast.py's run_benchmark_episode/run_rl_episode -- if you're
running an older results file without it, rerun the backtest first).

Usage:
    python evaluation/ticker_breakdown.py --results evaluation/results.csv
    python evaluation/ticker_breakdown.py --results evaluation/results.csv --side sell --benchmark twap
"""

import argparse
import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default="evaluation/results.csv")
    parser.add_argument("--side", default="sell", choices=["buy", "sell"])
    parser.add_argument("--benchmark", default="twap", choices=["twap", "vwap", "ac"])
    parser.add_argument("--min-episodes", type=int, default=3,
                         help="Skip tickers with fewer than this many episodes (too noisy to trust)")
    args = parser.parse_args()

    df = pd.read_csv(args.results)

    if "ticker" not in df.columns:
        raise SystemExit(
            "No 'ticker' column in this results file. Rerun the backtest with the "
            "updated backtest_fast.py (which records env.ticker per episode) first."
        )

    # Handle either label depending on whether this file went through run.py's
    # relabel step (rl_fast -> rl) or not.
    rl_label = "rl" if "rl" in df["strategy"].unique() else "rl_fast"

    rl = df[(df["strategy"] == rl_label) & (df["side"] == args.side)]
    bench = df[(df["strategy"] == args.benchmark) & (df["side"] == args.side)]

    if rl.empty or bench.empty:
        raise SystemExit(
            f"No rows found for strategy={rl_label}/{args.benchmark}, side={args.side}. "
            f"Available strategies: {df['strategy'].unique().tolist()}, "
            f"sides: {df['side'].unique().tolist()}"
        )

    rl_by_ticker = rl.groupby("ticker")["is_bps"].agg(["mean", "std", "count"])
    bench_by_ticker = bench.groupby("ticker")["is_bps"].agg(["mean", "std", "count"])

    combined = rl_by_ticker.join(bench_by_ticker, lsuffix="_rl", rsuffix="_bench", how="inner")
    combined = combined[(combined["count_rl"] >= args.min_episodes) &
                         (combined["count_bench"] >= args.min_episodes)]

    combined["diff_bps"] = combined["mean_bench"] - combined["mean_rl"]
    combined["pct_improvement"] = combined["diff_bps"] / (combined["mean_bench"].abs() + 1e-9) * 100

    combined = combined.sort_values("pct_improvement")

    print(f"\n=== [{args.side.upper()}] RL vs {args.benchmark.upper()} by ticker ===")
    print(f"(tickers with < {args.min_episodes} episodes excluded as too noisy)\n")
    display_cols = ["mean_rl", "mean_bench", "diff_bps", "pct_improvement", "count_rl"]
    print(combined[display_cols].round(2).to_string())

    print("\n--- Worst 3 tickers (lowest improvement, or negative) ---")
    print(combined[display_cols].round(2).head(3).to_string())

    print("\n--- Best 3 tickers (highest improvement) ---")
    print(combined[display_cols].round(2).tail(3).to_string())

    n_negative = (combined["pct_improvement"] < 0).sum()
    n_total = len(combined)
    print(f"\n{n_negative}/{n_total} tickers show RL underperforming {args.benchmark.upper()} "
          f"on {args.side} (negative improvement).")

    out_path = args.results.replace(".csv", f"_ticker_breakdown_{args.side}_{args.benchmark}.csv")
    combined.to_csv(out_path)
    print(f"\nFull breakdown saved to {out_path}")


if __name__ == "__main__":
    main()