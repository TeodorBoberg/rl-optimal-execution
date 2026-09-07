import pandas as pd

df = pd.read_csv("evaluation/results.csv")

sell_rl = df[(df["strategy"] == "rl") & (df["side"] == "sell")]

print("unfilled_fraction:")
print(sell_rl["unfilled_fraction"].describe())
print()
print("avg_participation_rate:")
print(sell_rl["avg_participation_rate"].describe())