"""
evaluation/calibrate_fold.py   (STAGE 3)

Re-calibrates the simulator separately for each walk-forward fold, using
ONLY that fold's training days, and writes configs/stage3/fold{k}.yaml.

Why: every calibrated number so far (average spread, per-ticker ADV, the
intraday volume profile used by VWAP / volume-clock benchmarks, the Hawkes
decay, the regime parameters) was measured once on the full sample --
including each fold's test days. That is a small look-ahead. Here each fold
only gets numbers it could have measured at the time.

What is measured on the training days of each fold:
  market.avg_spread_bps        mean real quoted spread (outliers clipped at the 99.5% quantile)
  market.ticker_adv            mean daily volume per ticker  (overrides load_csv_data's
                               ticker_adv column, which uses ALL days in the file)
  market.avg_daily_volume      mean of the per-ticker ADVs
  market.volatility_per_min    std of 1-minute mid log-returns (within-day, pooled)
  market.calm_vol / volatile_vol / prob_*   2-state Gaussian mixture on the log of the
                               15-minute rolling mean |return| (as calibrate_regime.py)
  market.hawkes_decay          exponential fit to the ACF of within-day-demeaned
                               log(volume share / profile)   (as calibrate_hawkes_decay.py)
  data.volume_profile_path     intraday volume profile -> configs/stage3/profile_fold{k}.csv

Plus the Stage 3 simulator switches:
  market.spread_source = data  the spread PAID each minute is that minute's real spread
  market.vol_source    = data  volatility = realised vol of the real midpoint, last 15 min
  execution.urgency_power      urgency = U ** p in training (default 2: more patient episodes)
  execution.spread_obs_ref     running: the agent's spread inputs are measured against the
                               quotes seen so far in the order, not a fixed calibrated level

It also writes evaluation/stage3_calibration.md comparing, per fold, the
full-sample value with the training-only value, so the size of the
look-ahead is visible.

With --unseen-groups N it also writes configs/stage3_unseen/g{j}_train.yaml
and g{j}_eval.yaml for fold --unseen-fold: the tickers are split into N
groups; each "train" config drops one group, its "eval" config keeps only it.

Usage:
    python evaluation/calibrate_fold.py
    python evaluation/calibrate_fold.py --folds 0,1,2,3 --base configs/stage2_np_sq_ho --unseen-groups 4
"""
import argparse
import contextlib
import copy
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


# ------------------------------------------------------------------
# Measurements (each takes a dataframe of whole ticker-days)
# ------------------------------------------------------------------
def _mid(df):
    if {"bid", "ask"}.issubset(df.columns):
        m = (df["bid"].astype(float) + df["ask"].astype(float)) / 2.0
        bad = ~np.isfinite(m) | (m <= 0)
        return m.where(~bad, df["close"].astype(float))
    return df["close"].astype(float)


def _key(df):
    return ["ticker", "day"] if "ticker" in df.columns else ["day"]


def m_spread(df):
    s = df["spread_bps"].astype(float)
    s = s[np.isfinite(s) & (s > 0)]
    hi = s.quantile(0.995)
    return float(s.clip(upper=hi).mean())


def m_adv(df):
    if "ticker" not in df.columns:
        return {}
    dv = df.groupby(["ticker", "day"])["volume"].sum()
    return {str(t): float(v) for t, v in dv.groupby("ticker").mean().items()}


def _returns(df):
    d = df[_key(df)].copy()
    d["lm"] = np.log(np.maximum(_mid(df).values, 1e-9))
    d["r"] = d.groupby(_key(df))["lm"].diff()
    return d


def m_vol(df):
    r = _returns(df)["r"].dropna()
    r = r[np.isfinite(r)]
    return float(r.std())


def m_regime(df, window=15):
    d = _returns(df)
    d["a"] = d["r"].abs()
    d["roll"] = d.groupby(_key(df))["a"].transform(lambda x: x.rolling(window, min_periods=window).mean())
    d = d.dropna(subset=["roll"])
    d = d[d["roll"] > 0]
    x = np.log(d["roll"].values).reshape(-1, 1)
    try:
        from sklearn.mixture import GaussianMixture
        gm = GaussianMixture(2, random_state=0).fit(x)
        lab = gm.predict(x)
        calm_lab = int(np.argmin(gm.means_.ravel()))
        calm = lab == calm_lab
        method = "gmm"
    except Exception:                       # sklearn missing: split at the 80% quantile
        calm = x.ravel() <= np.quantile(x.ravel(), 0.8)
        method = "quantile"
    d["calm"] = calm
    calm_vol = float(d.loc[d["calm"], "r"].std())
    volatile_vol = float(d.loc[~d["calm"], "r"].std())
    # transitions counted within each ticker-day only
    prev = d.groupby(_key(df))["calm"].shift()
    ok = prev.notna()
    pc, cc = prev[ok].astype(bool), d.loc[ok, "calm"].astype(bool)
    n_c, n_v = int(pc.sum()), int((~pc).sum())
    p_cv = float(((pc) & (~cc)).sum() / max(n_c, 1))
    p_vc = float(((~pc) & (cc)).sum() / max(n_v, 1))
    return dict(calm_vol=calm_vol, volatile_vol=volatile_vol,
                prob_calm_to_volatile=p_cv, prob_volatile_to_calm=p_vc,
                share_calm=float(d["calm"].mean()), method=method)


def m_profile(df, n_steps):
    d = df[_key(df) + ["volume"]].copy()
    d["step"] = d.groupby(_key(df)).cumcount()
    d = d[d["step"] < n_steps]
    tot = d.groupby(_key(df))["volume"].transform("sum")
    d["share"] = d["volume"] / tot.replace(0, np.nan)
    prof = d.groupby("step")["share"].mean().reindex(range(n_steps)).fillna(0.0).values
    prof = np.maximum(prof, 1e-12)
    return prof / prof.sum()


def m_hawkes(df, profile, max_lag=60, fit_lag=30):
    """Same method as simulator/calibrate_hawkes_decay.py: residual =
    log((volume share + 1e-9) / (profile + 1e-9)) per ticker-day, demeaned
    within the day, ACF pooled over ALL (t, t+lag) pairs (np.corrcoef),
    exponential fit on lags 1..fit_lag. Days of the wrong length are skipped."""
    n = len(profile)
    res = []
    for _, g in df.groupby(_key(df)):
        v = g["volume"].values.astype(float)
        if len(v) != n or v.sum() <= 0:
            continue
        z = np.log((v / v.sum() + 1e-9) / (profile + 1e-9))
        res.append(z - z.mean())
    acf = np.full(max_lag + 1, np.nan)
    for k in range(1, max_lag + 1):
        x = np.concatenate([z[:-k] for z in res])
        y = np.concatenate([z[k:] for z in res])
        acf[k] = np.corrcoef(x, y)[0, 1]
    lags = np.arange(1, fit_lag + 1)
    y = acf[1:fit_lag + 1]
    try:
        from scipy.optimize import curve_fit
        (a, b), _ = curve_fit(lambda t, a, b: a * np.exp(-b * t), lags, y,
                              p0=[0.3, 0.1], bounds=([0, 0], [2, 5]))
        return float(b), float(a), acf
    except Exception:
        return float("nan"), float("nan"), acf


def measure(df, n_steps):
    prof = m_profile(df, n_steps)
    decay, amp, acf = m_hawkes(df, prof)
    reg = m_regime(df)
    adv = m_adv(df)
    return dict(avg_spread_bps=m_spread(df),
                ticker_adv=adv,
                avg_daily_volume=float(np.mean(list(adv.values()))) if adv
                else float(df.groupby("day")["volume"].sum().mean()),
                volatility_per_min=m_vol(df),
                hawkes_decay=decay, hawkes_amp=amp,
                hawkes_acf={k: float(acf[k]) for k in (1, 5, 15, 30, 60)},
                profile=prof, **reg)


# ------------------------------------------------------------------
def set_key(cfg, sec, key, val):
    cfg.setdefault(sec, {})
    if cfg[sec] is None:
        cfg[sec] = {}
    cfg[sec][key] = val


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", default="0,1,2,3")
    ap.add_argument("--base", default="configs/stage2_np_sq_ho",
                    help="Directory with the configs to start from (fold{k}.yaml).")
    ap.add_argument("--out-dir", default="configs/stage3")
    ap.add_argument("--urgency-power", type=float, default=2.0)
    ap.add_argument("--spread-obs-ref", default="running",
                    help="execution.spread_obs_ref: 'running' = spread inputs relative to the "
                         "quotes seen so far in the order (robust to spreads drifting over time); "
                         "'global' = the original fixed reference.")
    ap.add_argument("--train-guard", default=None, metavar="BAND,STEPS",
                    help="Train with the schedule guardrail, e.g. 0.05,10 (Stage 3b).")
    ap.add_argument("--drop-spread-level", action="store_true",
                    help="Zero the slow spread-level input (Stage 3b).")
    ap.add_argument("--unseen-dir", default=None,
                    help="Where the unseen-ticker configs go (default: <out-dir>_unseen).")
    ap.add_argument("--no-data-spread", action="store_true",
                    help="Keep the model spread / regime volatility (calibration only).")
    ap.add_argument("--unseen-groups", type=int, default=0)
    ap.add_argument("--unseen-fold", type=int, default=3)
    ap.add_argument("--report", default="evaluation/stage3_calibration.md")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    folds = [int(x) for x in args.folds.split(",") if x.strip()]
    lines = ["# Stage 3 per-fold calibration", "",
             "Each fold re-measured on its TRAINING days only (train = everything the "
             "walk-forward split does not hold out; the validation tail used for "
             "checkpoint selection is part of it, which is fine -- it precedes the test days). "
             "`full` = the same measurement on every day in the fold's file, i.e. what a "
             "single full-sample calibration gives.", ""]
    tickers_all = None

    for k in folds:
        src = f"{args.base}/fold{k}.yaml"
        with open(src) as f:
            cfg = yaml.safe_load(f)
        dcfg, ecfg = cfg["data"], cfg["execution"]
        n_steps = int(ecfg["total_steps"])
        full = load_csv_data(dcfg["path"], ecfg["step_duration_min"])
        with contextlib.redirect_stdout(io.StringIO()):
            train, test = train_test_split_days(full, test_frac=dcfg.get("test_frac", 0.2))
        if "ticker" in full.columns and tickers_all is None:
            tickers_all = sorted(full["ticker"].astype(str).unique())
        print(f"fold {k}: {train.groupby(_key(train)).ngroups} train ticker-days, "
              f"{test.groupby(_key(test)).ngroups} test ticker-days")
        mf = measure(full, n_steps)
        mt = measure(train, n_steps)

        prof_path = f"{args.out_dir}/profile_fold{k}.csv"
        pd.DataFrame({"step": np.arange(n_steps), "volume_fraction": mt["profile"]}).to_csv(
            prof_path, index=False)

        out = copy.deepcopy(cfg)
        for key in ["avg_spread_bps", "avg_daily_volume", "volatility_per_min",
                    "calm_vol", "volatile_vol", "prob_calm_to_volatile", "prob_volatile_to_calm"]:
            set_key(out, "market", key, round(float(mt[key]), 8))
        if np.isfinite(mt["hawkes_decay"]):
            set_key(out, "market", "hawkes_decay", round(float(mt["hawkes_decay"]), 6))
        set_key(out, "market", "ticker_adv", {t: round(v, 1) for t, v in mt["ticker_adv"].items()})
        if not args.no_data_spread:
            set_key(out, "market", "spread_source", "data")
            set_key(out, "market", "vol_source", "data")
            set_key(out, "market", "vol_window", 15)
        set_key(out, "data", "volume_profile_path", prof_path)
        set_key(out, "execution", "urgency_power", float(args.urgency_power))
        set_key(out, "execution", "spread_obs_ref", args.spread_obs_ref)
        if args.train_guard:
            b, st = args.train_guard.split(",")
            set_key(out, "execution", "train_guard_band", float(b))
            set_key(out, "execution", "train_guard_steps", int(st))
        if args.drop_spread_level:
            set_key(out, "execution", "drop_spread_level", True)
        dst = f"{args.out_dir}/fold{k}.yaml"
        with open(dst, "w") as f:
            yaml.safe_dump(out, f, sort_keys=False)
        print(f"  wrote {dst}, {prof_path}")

        old = cfg.get("market", {})
        lines += [f"## Fold {k}", "",
                  "| parameter | config before | full sample | train only | train vs full |",
                  "|---|---:|---:|---:|---:|"]
        for key in ["avg_spread_bps", "avg_daily_volume", "volatility_per_min", "calm_vol",
                    "volatile_vol", "prob_calm_to_volatile", "prob_volatile_to_calm", "hawkes_decay"]:
            a, b = mf[key], mt[key]
            rel = (b / a - 1) * 100 if a else float("nan")
            ov = old.get(key, "")
            lines.append(f"| {key} | {ov} | {a:.6g} | {b:.6g} | {rel:+.1f}% |")
        lines.append("| volume ACF lag 1/5/15/30/60 (train) | | | "
                     + " / ".join(f"{mt['hawkes_acf'][q]:.3f}" for q in (1, 5, 15, 30, 60))
                     + f" (fit amplitude {mt['hawkes_amp']:.3f}) | |")
        pd_diff = np.abs(mt["profile"] - mf["profile"]).sum() / 2
        lines.append(f"| volume profile (total variation distance) | | | | {pd_diff*100:.2f}% |")
        lines.append(f"| regime method / calm share (train) | | | {mt['method']} / "
                     f"{mt['share_calm']:.2f} | |")
        lines += ["", "Per-ticker ADV, train-only vs full sample:", "",
                  "| ticker | full | train only | diff |", "|---|---:|---:|---:|"]
        for t in sorted(mf["ticker_adv"]):
            a, b = mf["ticker_adv"][t], mt["ticker_adv"].get(t, float("nan"))
            lines.append(f"| {t} | {a:,.0f} | {b:,.0f} | {(b/a-1)*100:+.1f}% |")
        lines.append("")

    if args.unseen_groups and tickers_all:
        k = args.unseen_fold
        g_n = args.unseen_groups
        groups = [tickers_all[j::g_n] for j in range(g_n)]
        udir = args.unseen_dir or (args.out_dir.rstrip("/\\") + "_unseen")
        os.makedirs(udir, exist_ok=True)
        with open(f"{args.out_dir}/fold{k}.yaml") as f:
            base = yaml.safe_load(f)
        lines += ["## Unseen-ticker groups (fold %d)" % k, ""]
        for j, g in enumerate(groups):
            tr = copy.deepcopy(base)
            set_key(tr, "data", "exclude_tickers", list(g))
            ev = copy.deepcopy(base)
            set_key(ev, "data", "tickers", list(g))
            for name, c in [("train", tr), ("eval", ev)]:
                with open(f"{udir}/g{j}_{name}.yaml", "w") as f:
                    yaml.safe_dump(c, f, sort_keys=False)
            lines.append(f"- group {j}: {', '.join(g)}  ->  {udir}/g{j}_train.yaml (without them), "
                         f"{udir}/g{j}_eval.yaml (only them)")
            print(f"  group {j}: {g}")
        lines.append("")

    os.makedirs(os.path.dirname(args.report), exist_ok=True)
    with open(args.report, "w") as f:
        f.write("\n".join(lines))
    print(f"\nwrote {args.report}")


if __name__ == "__main__":
    main()