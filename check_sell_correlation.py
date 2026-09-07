import pandas as pd

df = pd.read_csv("evaluation/results.csv")

sell_rl = df[(df["strategy"] == "rl") & (df["side"] == "sell")]

print("Correlation between unfilled_fraction and is_bps (cost):")
print(sell_rl[["unfilled_fraction", "is_bps"]].corr())
print()

print("Cost for fully-filled episodes (unfilled_fraction == 0):")
print(sell_rl[sell_rl["unfilled_fraction"] == 0]["is_bps"].describe())
print()

print("Cost for partially-unfilled episodes (unfilled_fraction > 0):")
print(sell_rl[sell_rl["unfilled_fraction"] > 0]["is_bps"].describe())