"""
evaluation/diagnose_low_urgency.py   (STAGE 3)

Why does the agent WITHOUT the guardrail fail at low urgency, mostly in
fold 1? For each paired episode it compares the agent (mean over model
seeds) with TWAP on the same ticker-day and price path, and links the gap to
what that test day looked like against the fold's TRAINING calibration:

    vol_ratio    = ticker-day volume / training ADV of that ticker
    spread_ratio = ticker-day mean spread / training avg_spread_bps
    open_ratio   = mean spread in the first 30 min / that day's mean spread

Prints, per fold: the cost gap split into execution / drift / permanent /
fees, how far through the order the agent is at 25 / 50 / 75 % of the day
(TWAP is 25 / 50 / 75 %), and the gap by tercile of each day feature.

Usage:
    python evaluation/diagnose_low_urgency.py --run evaluation/stage3 --urgency 0
    python evaluation/diagnose_low_urgency.py --run evaluation/stage3 --urgency 0.25 --config-pattern "configs/stage3/fold{fold}.yaml"
"""
import argparse
import contextlib
import io
import os
import sys

import numpy as np
import pandas as pd
import yaml

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_root)
sys.path.insert(0, _root)

from simulator.synthetic_data import load_csv_data          # noqa: E402
from simulator.data_split import train_test_split_days      # noqa: E402

KEY = ["fold", "side", "episode"]
COMP = ["is_signed_bps", "execution_bps", "drift_bps", "permanent_bps", "fees_bps"]


def day_features(cfg_path):
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)
    full = load_csv_data(cfg["data"]["path"], cfg["execution"]["step_duration_min"])
    with contextlib.redirect_stdout(io.StringIO()):
        _, test = train_test_split_days(full, test_frac=cfg["data"].get("test_frac", 0.2))
    m = cfg["market"]
    adv = m.get("ticker_adv") or {}
    avg_spread = float(m["avg_spread_bps"])
    test = test.copy()
    test["step"] = test.groupby(["ticker", "day"]).cumcount()
    g = test.groupby(["ticker", "day"])
    f = pd.DataFrame({
        "volume": g["volume"].sum(),
        "spread": g["spread_bps"].mean(),
        "open_spread": test[test.step < 30].groupby(["ticker", "day"])["spread_bps"].mean(),
    }).reset_index()
    f["ticker"] = f["ticker"].astype(str)
    f["vol_ratio"] = f["volume"] / f["ticker"].map(lambda t: adv.get(t, np.nan))
    f["spread_ratio"] = f["spread"] / avg_spread
    f["open_ratio"] = f["open_spread"] / f["spread"]
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="evaluation/stage3")
    ap.add_argument("--urgency", type=float, default=0.0)
    ap.add_argument("--config-pattern", default="configs/stage3/fold{fold}.yaml")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    ep = pd.read_csv(os.path.join(args.run, "episodes.csv"))
    ru = pd.read_csv(os.path.join(args.run, "rl_urgency_paired.csv"))
    rl = ru[np.isclose(ru.urgency_setting, args.urgency)]
    if rl.empty:
        raise SystemExit(f"no RL rows at urgency {args.urgency}")
    cols = [c for c in COMP + ["done_25", "done_50", "done_75", "finish_step",
                               "avg_participation", "unfilled_frac"] if c in rl.columns]
    rlm = rl.groupby(KEY + ["ticker", "day"])[cols].mean().reset_index()
    tw = ep[ep.strategy == "twap"][KEY + cols]
    m = rlm.merge(tw, on=KEY, suffixes=("", "_twap"))
    for c in COMP:
        m["d_" + c.replace("_bps", "")] = m[c] - m[c + "_twap"]
    m["ticker"] = m["ticker"].astype(str)

    feats = []
    for k in sorted(m.fold.unique()):
        f = day_features(args.config_pattern.format(fold=k))
        f["fold"] = k
        feats.append(f)
    feats = pd.concat(feats, ignore_index=True)
    m = m.merge(feats, on=["fold", "ticker", "day"], how="left")
    miss = m.vol_ratio.isna().mean()

    R = [f"# Agent (no guardrail) vs TWAP at urgency {args.urgency:g}, paired episodes", "",
         f"Run: `{args.run}`. Gap = agent - TWAP in bps, positive = agent worse. "
         f"Agent averaged over model seeds. Unmatched days: {miss:.1%}.", "",
         "## Per fold", "",
         "| fold | episodes | gap | execution | drift | permanent | fees | done@25% | done@50% | done@75% | finish step | participation | test vol / train ADV | test spread / train avg |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for k, g in m.groupby("fold"):
        R.append(f"| {k} | {len(g)} | {g.d_is_signed.mean():+.2f} | {g.d_execution.mean():+.2f} | "
                 f"{g.d_drift.mean():+.2f} | {g.d_permanent.mean():+.2f} | {g.d_fees.mean():+.2f} | "
                 f"{g.done_25.mean():.0%} | {g.done_50.mean():.0%} | {g.done_75.mean():.0%} | "
                 f"{g.finish_step.mean():.0f} | {g.avg_participation.mean():.3f} | "
                 f"{g.vol_ratio.median():.2f} | {g.spread_ratio.median():.2f} |")

    for feat, label in [("vol_ratio", "day volume / training ADV"),
                        ("spread_ratio", "day mean spread / training average spread"),
                        ("open_ratio", "first-30-min spread / day mean spread")]:
        R += ["", f"## Gap by tercile of {label} (terciles within each fold)", "",
              "| fold | low | mid | high | corr(gap, log feature) |", "|---|---:|---:|---:|---:|"]
        for k, g in m.dropna(subset=[feat]).groupby("fold"):
            g = g.copy()
            try:
                g["b"] = pd.qcut(g[feat], 3, labels=["low", "mid", "high"])
            except ValueError:
                continue
            t = g.groupby("b", observed=False).d_is_signed.mean()
            c = np.corrcoef(g.d_is_signed, np.log(g[feat].clip(lower=1e-9)))[0, 1]
            R.append(f"| {k} | {t['low']:+.2f} | {t['mid']:+.2f} | {t['high']:+.2f} | {c:+.2f} |")

    R += ["", "## Worst tickers (all folds)", "", "| ticker | episodes | gap |", "|---|---:|---:|"]
    for tk, g in m.groupby("ticker").d_is_signed.agg(["count", "mean"]).sort_values("mean",
                                                                               ascending=False).iterrows():
        R.append(f"| {tk} | {int(g['count'])} | {g['mean']:+.2f} |")

    out = args.out or os.path.join(args.run, f"diagnose_u{args.urgency:g}.md")
    with open(out, "w") as f:
        f.write("\n".join(R) + "\n")
    print("\n".join(R))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()