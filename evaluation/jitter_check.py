"""
evaluation/jitter_check.py

How evenly does each strategy trade? Reads traces.csv written by
batch1_eval.py and reports, over minutes where the order is still open:

  size swing    typical minute-to-minute change in trade size, as a ratio
                (median of exp|diff log size|): 1.0 = perfectly smooth
                (TWAP); POV 20% is ~1.6x because it follows each minute's volume
  idle share    fraction of those minutes in which nothing was traded

Trade size is reconstructed as participation x the minute's volume (the
next row's lagged volume ratio is this minute's volume).

Usage:
    python evaluation/jitter_check.py evaluation/stage1_np evaluation/stage1_np_sq
"""
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_root)

import numpy as np
import pandas as pd

K = ["fold", "strategy", "model_seed", "side", "episode"]

for d in sys.argv[1:] or ["evaluation/batch1"]:
    t = pd.read_csv(os.path.join(d, "traces.csv")).sort_values(K + ["step"])
    t["q"] = t.participation * t.groupby(K).lag_volume_ratio.shift(-1)
    live = t[t.remaining_frac_before > 0.01].copy()
    idle = (live.participation <= 0).groupby(live.strategy).mean()
    p = live[live.q > 0].copy()
    p["dl"] = p.groupby(K).q.transform(lambda s: np.log(s).diff().abs())
    swing = np.exp(p.groupby("strategy").dl.median())
    out = pd.DataFrame({"size swing (x)": swing, "idle share": idle}).round(3)
    print(f"\n{d}\n{out.to_string()}")