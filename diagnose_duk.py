"""
diagnose_duk.py

Determines whether DUK's catastrophic sell-side RL performance (mean 580
bps, std 832, vs 44/55 for all other tickers) is:
  (a) a data quality issue specific to DUK, or
  (b) a genuine sell-side modeling asymmetry in the simulator.

Key evidence to weigh: DUK is RL's SECOND-BEST ticker on buys (+60%)
while being catastrophic on sells -- same policy, same data, opposite
sides. That asymmetry is what makes this worth isolating.
"""

import pandas as pd
import numpy as np

results = pd.read_csv("evaluation/results.csv")
rl_label = "rl" if "rl" in results["strategy"].unique() else "rl_fast"

duk = results[results["ticker"].str.lower() == "duk"]

print("=== DUK cost distribution by strategy and side ===")
print(duk.groupby(["strategy", "side"])["is_bps"].agg(
    ["mean", "std", "median", "min", "max", "count"]).round(2).to_string())

print("\n=== DUK RL sell episodes: worst 10 ===")
duk_rl_sell = duk[(duk.strategy == rl_label) & (duk.side == "sell")].nlargest(10, "is_bps")
cols = [c for c in ["episode", "is_bps", "avg_slippage_bps", "avg_participation_rate",
                     "unfilled_fraction", "total_cost_dollars"] if c in duk_rl_sell.columns]
print(duk_rl_sell[cols].round(3).to_string(index=False))

print("\n=== How concentrated is the damage? ===")
rl_sell_all = results[(results.strategy == rl_label) & (results.side == "sell")]
duk_sell = rl_sell_all[rl_sell_all["ticker"].str.lower() == "duk"]["is_bps"]
sorted_costs = duk_sell.sort_values(ascending=False)
for k in [1, 3, 5, 10]:
    if len(sorted_costs) >= k:
        topk_total = sorted_costs.head(k).sum()
        all_total = rl_sell_all["is_bps"].sum()
        print(f"  DUK's worst {k:2d} sell episode(s) account for "
              f"{topk_total/all_total:.1%} of TOTAL RL sell cost across ALL 14 tickers")

print("\n=== Underlying market data check for DUK ===")
bars = pd.read_csv("data/combined_1m_clean.csv")
duk_bars = bars[bars["ticker"].str.lower() == "duk"]
others = bars[bars["ticker"].str.lower() != "duk"]

for label, d in [("DUK", duk_bars), ("All others", others)]:
    zero_vol = (d["volume"] == 0).mean()
    print(f"  {label:12s}: zero-volume minutes={zero_vol:.2%}, "
          f"median spread_bps={d['spread_bps'].median():.2f}, "
          f"median volume={d['volume'].median():.0f}, "
          f"volume p10={d['volume'].quantile(0.1):.0f}")

# Intraday price range -- large adverse moves would hurt sells specifically
print("\n=== Intraday price movement (matters asymmetrically for buy vs sell) ===")
for label, d in [("DUK", duk_bars), ("All others", others)]:
    daily = d.groupby(["ticker", "day"])["close"].agg(["first", "last", "min", "max"])
    daily["day_return_pct"] = (daily["last"] / daily["first"] - 1) * 100
    daily["intraday_range_pct"] = (daily["max"] / daily["min"] - 1) * 100
    print(f"  {label:12s}: mean day return={daily['day_return_pct'].mean():+.3f}%, "
          f"std={daily['day_return_pct'].std():.3f}%, "
          f"mean intraday range={daily['intraday_range_pct'].mean():.3f}%")