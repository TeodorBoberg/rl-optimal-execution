"""
evaluation/measure_spread.py

How much does the spread really vary minute to minute, and does the
simulator reproduce it?

The final result's edge over spread-unaware schedules comes from the agent
trading less when the quoted spread is wide. In the simulator that variation
comes from an ASSUMED model (DynamicSpreadModel: time-of-day, volatility and
depth multipliers, plus "news windows" in 2% of minutes with the spread x5).
This script measures the same quantities on the real 1-minute bars and on
the simulator's quoted spread, side by side.

Per ticker-day, spreads are expressed relative to that ticker-day's median
(r = spread / median), so the comparison is about VARIATION, not level.

Reported for both:
  quantiles of r, share of minutes with r > 1.5 / 2 / 3 / 5
  persistence: autocorrelation of log r at lags 1, 5, 15 minutes (within day)
               -- lag 1 is what a trader can exploit: how well the last
               minute's spread predicts this minute's
  intraday shape: median r per 30-minute bucket
  link to volatility: correlation of log r with log 15-minute realised vol

Usage:
    python evaluation/measure_spread.py --data data/combined_1m_clean.csv
    python evaluation/measure_spread.py --data data/combined_1m_clean.csv --sim-days 300
"""

import argparse
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
os.chdir(_root)

import numpy as np
import pandas as pd
import yaml

KEY = ["ticker", "day"]


def spread_stats(df, label):
    """df: columns ticker, day, step, spread, price. One row per minute."""
    df = df[np.isfinite(df.spread) & (df.spread > 0)].copy()
    df = df.sort_values(KEY + ["step"])
    med = df.groupby(KEY).spread.transform("median")
    df["r"] = df.spread / med
    df["lr"] = np.log(df.r)
    g = df.groupby(KEY)
    out = {"label": label, "ticker_days": g.ngroups, "minutes": len(df),
           "median spread (bps)": float(df.spread.median())}
    q = df.r.quantile([0.05, 0.25, 0.75, 0.95, 0.99])
    for k, v in q.items():
        out[f"r p{int(k * 100)}"] = float(v)
    for thr in (1.5, 2, 3, 5):
        out[f"share r>{thr:g}"] = float((df.r > thr).mean())
    for lag in (1, 5, 15):
        prev = g.lr.shift(lag)
        ok = prev.notna()
        out[f"acf lag {lag}"] = float(np.corrcoef(df.lr[ok], prev[ok])[0, 1])
    # realised volatility over the previous 15 minutes
    ret = g.price.transform(lambda s: np.log(s).diff())
    df["rv"] = ret.abs().groupby([df.ticker, df.day]).transform(
        lambda s: s.rolling(15, min_periods=10).mean())
    ok = df.rv > 0
    out["corr(log r, log vol15)"] = float(np.corrcoef(df.lr[ok], np.log(df.rv[ok]))[0, 1])
    shape = df.groupby(df.step // 30).r.median()
    return out, shape


def real_frame(path, max_days, seed):
    df = pd.read_csv(path)
    keys = df[KEY].drop_duplicates()
    if max_days and len(keys) > max_days:
        keys = keys.sample(max_days, random_state=seed)
        df = df.merge(keys, on=KEY)
    if {"bid", "ask"}.issubset(df.columns):
        price = (df.bid + df.ask) / 2
        price = price.where(price > 0, df.close)
    else:
        price = df.close
    if "step" not in df.columns:
        df["step"] = df.groupby(KEY).cumcount()
    return pd.DataFrame({"ticker": df.ticker, "day": df.day, "step": df.step,
                         "spread": df.spread_bps, "price": price})


def sim_frame(cfg_path, overrides, n_days, seed):
    """Quoted spread from the simulator's order book, no trading."""
    from agent.env import ExecutionEnv
    from simulator.synthetic_data import load_csv_data
    from evaluation.batch1_eval import set_overrides_env, apply_overrides
    set_overrides_env(overrides)
    with open(cfg_path) as f:
        cfg = apply_overrides(yaml.safe_load(f))
    data = load_csv_data(cfg["data"]["path"], cfg["execution"]["step_duration_min"])
    env = ExecutionEnv(cfg, data=data, side="buy", urgency=0.5)
    rows = []
    for i in range(n_days):
        env.reset(seed=seed + i)
        tk = getattr(env, "ticker", "x")
        for t in range(env.total_steps - 1):
            rows.append((tk, i, t, env.quoted_spread_bps(), env.sim.mid_price))
            env.sim.step()
    return pd.DataFrame(rows, columns=["ticker", "day", "step", "spread", "price"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=None,
                    help="Real bars to compare against. Default: the SAME file the simulator "
                         "config uses (data.path), so both columns describe the same market.")
    ap.add_argument("--max-days", type=int, default=2000,
                    help="Ticker-days sampled from the real data (0 = all).")
    ap.add_argument("--config", default="configs/walkforward/fold3.yaml",
                    help="Config for the simulator side.")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                    help="Config overrides for the simulator side (repeatable).")
    ap.add_argument("--sim-days", type=int, default=200,
                    help="Simulated days. 0 skips the simulator comparison.")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="evaluation/spread_report.md")
    args = ap.parse_args()

    if args.data is None:
        with open(args.config) as f:
            args.data = yaml.safe_load(f)["data"]["path"]
    print(f"real data: {args.data}   simulator config: {args.config}")
    stats, shapes = [], {}
    s, sh = spread_stats(real_frame(args.data, args.max_days, args.seed), "real data")
    stats.append(s); shapes["real data"] = sh
    if args.sim_days > 0:
        label = "simulator" + (f" ({', '.join(args.set)})" if args.set else "")
        s, sh = spread_stats(sim_frame(args.config, args.set, args.sim_days, args.seed), "simulator")
        stats.append(s); shapes["simulator"] = sh

    t = pd.DataFrame(stats).set_index("label").T
    R = ["# Spread variation: real data vs simulator\n",
         "r = spread / that ticker-day's median spread. Lag-k ACF is the within-day "
         "autocorrelation of log r: lag 1 is how well the previous minute's spread "
         "predicts this minute's, which is the information a trader can use.\n"]
    R.append(f"Real data: `{args.data}`. Simulator config: `{args.config}`.\n")
    if args.set:
        R.append(f"Simulator overrides: `{', '.join(args.set)}`\n")
    R.append("| statistic | " + " | ".join(t.columns) + " |")
    R.append("|---|" + "---|" * len(t.columns))
    for k, row in t.iterrows():
        cells = []
        for v in row:
            if k in ("ticker_days", "minutes") or isinstance(v, (int, np.integer)):
                cells.append(f"{int(v):,}")
            elif "share" in k:
                cells.append(f"{v * 100:.2f}%")
            else:
                cells.append(f"{v:.3f}")
        R.append(f"| {k} | " + " | ".join(cells) + " |")
    R.append("\n## Intraday shape (median r per 30-minute bucket)\n")
    sp = pd.DataFrame(shapes)
    sp.index = [f"{int(i) * 30}-{int(i) * 30 + 29}" for i in sp.index]
    R.append("| minutes | " + " | ".join(sp.columns) + " |")
    R.append("|---|" + "---|" * len(sp.columns))
    for i, row in sp.iterrows():
        R.append(f"| {i} | " + " | ".join(f"{v:.2f}" for v in row) + " |")
    txt = "\n".join(R) + "\n"
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(txt)
    print(txt)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()