import pandas as pd
import numpy as np

df = pd.read_csv("data/combined_1m.csv")
avg_vol_per_step = df.groupby("ticker")["volume"].sum() / (df.groupby("ticker")["day"].nunique() * 390)
df["avg_vol_per_step"] = df["ticker"].map(avg_vol_per_step)
df["vol_ratio"] = df["volume"] / df["avg_vol_per_step"]

# execute()'s cap: qty > step_volume * max_participation_rate gets clipped.
# qty = level * avg_vol_per_step, so capping triggers when vol_ratio < 4 * level
# (using max_participation_rate=0.25, the config default).
max_participation_rate = 0.25

print("Directly computed capping rate at each swept participation level:")
for level in [0.005, 0.01, 0.02, 0.05, 0.10, 0.25]:
    threshold = level / max_participation_rate
    frac_capped = (df["vol_ratio"] < threshold).mean()
    print(f"  level={level:.1%}: capping threshold vol_ratio<{threshold:.4f}, "
          f"fraction of real minutes below it: {frac_capped:.1%}")