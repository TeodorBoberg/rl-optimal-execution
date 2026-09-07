import pandas as pd
from scipy import stats

df = pd.read_csv("evaluation/results.csv")

for side in ["buy", "sell"]:
    side_df = df[df["side"] == side]
    rl = side_df[side_df["strategy"].isin(["rl", "rl_fast"])]["is_bps"].values
    print(f"\n=== {side.upper()} ===")
    for strategy in ["twap", "vwap", "ac"]:
        bench = side_df[side_df["strategy"] == strategy]["is_bps"].values
        n = min(len(rl), len(bench))
        t_stat, p_value = stats.ttest_ind(bench[:n], rl[:n])
        sig = "significant" if p_value < 0.05 else "NOT significant"
        print(f"  vs {strategy.upper():6s}: p={p_value:.4f}  ({sig} at 5%)")