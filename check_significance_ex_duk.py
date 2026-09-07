"""
check_significance_ex_duk.py

Re-runs the paired significance tests with and without DUK, to quantify
how much of the sell-side significance failure is attributable to that
one ticker (identified via ticker_breakdown.py as costing RL 200bps vs
TWAP on sells, while being RL's 2nd-BEST ticker on buys -- a strong
sell-specific asymmetry signal).
"""

import pandas as pd
import numpy as np
from scipy import stats

df = pd.read_csv("evaluation/results.csv")
rl_label = "rl" if "rl" in df["strategy"].unique() else "rl_fast"

if "ticker" not in df.columns:
    raise SystemExit("results.csv has no ticker column -- rerun the backtest first.")


def run_tests(data, label):
    print(f"\n=== {label} ===")
    for side in ["buy", "sell"]:
        for bench in ["twap", "vwap", "ac"]:
            rl = data[(data.strategy == rl_label) & (data.side == side)].sort_values("episode")
            bn = data[(data.strategy == bench) & (data.side == side)].sort_values("episode")
            # Pair on episode id so the paired test is valid
            merged = rl[["episode", "is_bps"]].merge(
                bn[["episode", "is_bps"]], on="episode", suffixes=("_rl", "_bench")
            )
            if len(merged) < 3:
                print(f"  [{side.upper()}] vs {bench.upper()}: too few paired episodes")
                continue
            diff = merged["is_bps_bench"] - merged["is_bps_rl"]
            t, p = stats.ttest_rel(merged["is_bps_bench"], merged["is_bps_rl"])
            sig = "significant" if p < 0.05 else "NOT significant"
            bonf = "PASSES" if p < 0.0083 else "fails"
            print(f"  [{side.upper()}] vs {bench.upper():5s}: mean_diff={diff.mean():+8.2f} bps, "
                  f"p={p:.4f} ({sig} at 5%, {bonf} Bonferroni), n={len(merged)}")


run_tests(df, "ALL TICKERS (baseline)")
run_tests(df[df["ticker"].str.lower() != "duk"], "EXCLUDING DUK")

# Show DUK's contribution to sell-side variance specifically
rl_sell = df[(df.strategy == rl_label) & (df.side == "sell")]
print(f"\n=== RL sell cost variance decomposition ===")
print(f"All tickers:    mean={rl_sell.is_bps.mean():8.2f}, std={rl_sell.is_bps.std():8.2f}, n={len(rl_sell)}")
ex_duk = rl_sell[rl_sell["ticker"].str.lower() != "duk"]
print(f"Excluding DUK:  mean={ex_duk.is_bps.mean():8.2f}, std={ex_duk.is_bps.std():8.2f}, n={len(ex_duk)}")
duk_only = rl_sell[rl_sell["ticker"].str.lower() == "duk"]
print(f"DUK only:       mean={duk_only.is_bps.mean():8.2f}, std={duk_only.is_bps.std():8.2f}, n={len(duk_only)}")