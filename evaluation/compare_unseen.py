"""
evaluation/compare_unseen.py   (STAGE 3: unseen stocks)

For each ticker group j, two evaluations on the SAME held-out tickers and
the SAME episodes (configs/stage3_unseen/g{j}_eval.yaml):
    unseen : model trained WITHOUT those tickers   (models/s3u_g{j}_f3_s*.zip)
    seen   : the normal Stage 3 model, trained on all tickers (models/s3_f3_s*.zip)

Cost difference unseen - seen, per urgency, per group and pooled, with a
bootstrap over trading days (episodes on the same ticker-day share a price
path). Positive = the agent is worse on stocks it never trained on.

Also prints each agent's gap to the best classical schedule on these tickers
(from the benchmark rows, which are identical in the two directories).

Usage:
    python evaluation/compare_unseen.py --groups 4
    python evaluation/compare_unseen.py --groups 4 --unseen evaluation\\stage3_unseen\\g{j}_unseen --seen evaluation\\stage3_unseen\\g{j}_seen
"""
import argparse
import os

import numpy as np
import pandas as pd

METRIC = "is_signed_bps"
KEY = ["fold", "side", "episode"]


def load_rl(d):
    ep = pd.read_csv(os.path.join(d, "episodes.csv"))
    rl = ep[ep.strategy == "rl"].copy()
    rl["urgency_setting"] = 0.5
    p = os.path.join(d, "rl_urgency_paired.csv")
    if os.path.exists(p):
        ru = pd.read_csv(p)
        if 0.5 in set(ru.urgency_setting.round(6)):
            rl = ru
        else:
            rl = pd.concat([ru, rl], ignore_index=True)
    rl["urgency_setting"] = rl["urgency_setting"].round(4)
    g = rl.groupby(KEY + ["urgency_setting"]).agg(cost=(METRIC, "mean"),
                                                     ticker=("ticker", "first"),
                                                     day=("day", "first")).reset_index()
    bench = ep[ep.strategy != "rl"]
    return g, bench


def boot_ci(diff, cluster, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({"d": diff, "c": cluster})
    by = df.groupby("c")["d"].agg(["sum", "count"])
    s, c = by["sum"].values, by["count"].values
    k = len(s)
    if k < 2:
        return np.nan, np.nan
    idx = rng.integers(0, k, size=(n, k))
    m = s[idx].sum(1) / c[idx].sum(1)
    return float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))


def best_classical(bench):
    """Lowest mean-cost benchmark at urgency 0.5 (episodes.csv benchmarks are run at 0.5)."""
    m = bench.groupby("strategy")[METRIC].mean()
    return m.idxmin(), float(m.min())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--groups", type=int, default=4)
    ap.add_argument("--unseen", default="evaluation/stage3_unseen/g{j}_unseen")
    ap.add_argument("--seen", default="evaluation/stage3_unseen/g{j}_seen")
    ap.add_argument("--out", default="evaluation/stage3_unseen/unseen_report.md")
    args = ap.parse_args()

    rows, pooled = [], []
    R = ["# Unseen stocks: agent trained without the tickers vs agent trained with them", "",
         "Same held-out tickers, same episodes, same benchmarks. "
         "`diff` = unseen - seen in bps of signed implementation shortfall "
         "(**positive = worse on stocks never seen in training**). "
         "95% CI from a bootstrap over ticker-days.", ""]
    for j in range(args.groups):
        du, ds = args.unseen.format(j=j), args.seen.format(j=j)
        if not (os.path.exists(os.path.join(du, "episodes.csv"))
                and os.path.exists(os.path.join(ds, "episodes.csv"))):
            print(f"group {j}: missing {du} or {ds}, skipped")
            continue
        u, bench = load_rl(du)
        s, _ = load_rl(ds)
        m = u.merge(s, on=KEY + ["urgency_setting"], suffixes=("_u", "_s"))
        if not (m.ticker_u == m.ticker_s).all() or not (m.day_u == m.day_s).all():
            raise SystemExit(f"group {j}: episodes are not paired (different ticker/day)")
        m["diff"] = m.cost_u - m.cost_s
        m["cluster"] = m.ticker_u.astype(str) + "_" + m.day_u.astype(str)
        m["group"] = j
        pooled.append(m)
        bname, bval = best_classical(bench)
        u05 = m[m.urgency_setting == 0.5]
        R.append(f"- group {j} ({', '.join(sorted(m.ticker_u.astype(str).unique()))}): "
                 f"at u=0.5 unseen {u05.cost_u.mean():.2f}, seen {u05.cost_s.mean():.2f}, "
                 f"best classical {bname} {bval:.2f} bps")
        for us, g in m.groupby("urgency_setting"):
            lo, hi = boot_ci(g["diff"].values, g["cluster"].values)
            rows.append(dict(group=j, urgency=us, n=len(g), unseen=g.cost_u.mean(),
                             seen=g.cost_s.mean(), diff=g["diff"].mean(), lo=lo, hi=hi))
    if not pooled:
        raise SystemExit("nothing to compare")
    allm = pd.concat(pooled, ignore_index=True)
    allm["cluster"] = allm["group"].astype(str) + "_" + allm["cluster"]
    for us, g in allm.groupby("urgency_setting"):
        lo, hi = boot_ci(g["diff"].values, g["cluster"].values)
        rows.append(dict(group="all", urgency=us, n=len(g), unseen=g.cost_u.mean(),
                         seen=g.cost_s.mean(), diff=g["diff"].mean(), lo=lo, hi=hi))
    # Raw cost differences mix in speed: two policies at the same urgency
    # setting can trade at different speeds (and so different risk). The
    # fair comparison is each model's gap to the classical frontier AT ITS
    # OWN RISK, from urgency_frontier_runs.csv (mean over model seeds).
    F = []
    for j in range(args.groups):
        du, ds = args.unseen.format(j=j), args.seen.format(j=j)
        pu, ps = (os.path.join(d, "urgency_frontier_runs.csv") for d in (du, ds))
        if not (os.path.exists(pu) and os.path.exists(ps)):
            continue
        a = pd.read_csv(pu).groupby("urgency")[["gap_best", "gap_best_sched", "risk"]].mean()
        b = pd.read_csv(ps).groupby("urgency")[["gap_best", "gap_best_sched", "risk"]].mean()
        nu = pd.read_csv(pu).seed.nunique()
        ns = pd.read_csv(ps).seed.nunique()
        for u in a.index.intersection(b.index):
            F.append(dict(group=j, urgency=u, seeds=f"{nu}/{ns}",
                          risk_u=a.loc[u, "risk"], risk_s=b.loc[u, "risk"],
                          gb_u=a.loc[u, "gap_best"], gb_s=b.loc[u, "gap_best"],
                          gs_u=a.loc[u, "gap_best_sched"], gs_s=b.loc[u, "gap_best_sched"]))
    t = pd.DataFrame(rows)
    R += ["", "| group | urgency | episodes | unseen | seen | diff | 95% CI |",
          "|---|---:|---:|---:|---:|---:|---|"]
    for _, r in t.iterrows():
        R.append(f"| {r.group} | {r.urgency:g} | {r.n} | {r.unseen:.2f} | {r.seen:.2f} | "
                 f"{r['diff']:+.2f} | [{r.lo:+.2f}, {r.hi:+.2f}] |")
    if F:
        f = pd.DataFrame(F)
        fa = f.groupby("urgency")[["risk_u", "risk_s", "gb_u", "gb_s", "gs_u", "gs_s"]].mean().reset_index()
        fa["group"], fa["seeds"] = "all", ""
        f = pd.concat([f, fa], ignore_index=True)
        R += ["", "## Gap to the classical frontier at each model's own risk (the fair comparison)", "",
              "Negative = cheaper than the best classical strategy at the same risk. "
              "`seeds` = model seeds averaged, unseen/seen. Raw cost differences above also "
              "contain any difference in trading speed; these do not.", "",
              "| group | urgency | seeds | risk unseen / seen | gap best classical: unseen | seen | "
              "unseen - seen | gap best schedule: unseen | seen |",
              "|---|---:|---|---|---:|---:|---:|---:|---:|"]
        for _, r in f.iterrows():
            R.append(f"| {r.group} | {r.urgency:g} | {r.seeds} | {r.risk_u:.1f} / {r.risk_s:.1f} | "
                     f"{r.gb_u:+.2f} | {r.gb_s:+.2f} | {r.gb_u - r.gb_s:+.2f} | "
                     f"{r.gs_u:+.2f} | {r.gs_s:+.2f} |")
    R += ["", "Per ticker, pooled over urgencies:", "", "| ticker | diff |", "|---|---:|"]
    for tk, g in allm.groupby("ticker_u"):
        R.append(f"| {tk} | {g['diff'].mean():+.2f} |")
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        f.write("\n".join(R) + "\n")
    print("\n".join(R))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()