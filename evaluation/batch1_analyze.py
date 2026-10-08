"""
evaluation/batch1_analyze.py

Turns the output of batch1_eval.py into the Batch 1 report:

  0. Metric check    -- clipped cost (every earlier result) vs signed
                        implementation shortfall, per strategy
  1. Headline        -- agent vs every benchmark, 12 runs, under both metrics
  2. Benchmark sweep -- AC and POV at every setting; agent vs the BEST one,
                        with the best chosen on other folds so the choice is
                        not fitted to the episodes it is scored on
  3. Frontier        -- mean cost vs cost dispersion (the Almgren-Chriss
                        picture); frontier.png
  4. Decomposition   -- drift / own permanent impact / execution / fees
  5. Significance    -- day-clustered bootstrap CIs, next to the naive t-test
  6. Behaviour       -- what the agent does, next to TWAP and POV 20%;
                        behaviour.png
  7. Urgency         -- completion profile at urgency 0 ... 1

Writes evaluation/batch1/report.md plus the PNGs. Every number in the
report is computed here; nothing is typed in by hand.

Usage:
    python evaluation/batch1_analyze.py
    python evaluation/batch1_analyze.py --in evaluation/batch1 --n-boot 2000
"""

import argparse
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_root)

import numpy as np
import pandas as pd
from scipy import stats

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Categorical colours in fixed order (validated default palette)
C_RL, C_AC, C_POV, C_TWAP, C_VWAP = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e6e5e0", "#fcfcfb"

HEADLINE = ["twap", "vwap", "ac@0.6", "pov@5", "pov@10", "pov@20"]
LABEL = {"twap": "TWAP", "vwap": "VWAP", "ac@0.6": "AC (preset, 0.6)",
         "pov@5": "POV 5%", "pov@10": "POV 10%", "pov@20": "POV 20%", "rl": "RL agent"}
METRICS = {"is_bps": "clipped (old)", "is_signed_bps": "signed IS"}


def lab(s):
    if s in LABEL:
        return LABEL[s]
    if s.startswith("ac@"):
        return f"AC ra={s[3:]}"
    if s.startswith("pov@"):
        return f"POV {s[4:]}%"
    if s.startswith("acv@"):
        return f"AC-volclock ra={s[4:]}"
    if s.startswith("acl@"):
        return f"AC-live ra={s[4:]}"
    if s.startswith("acs"):
        k, ra = s[3:].split("@")
        return f"AC-live spread k={k} ra={ra}"
    return s


def md_table(df, floatfmt="{:+.2f}"):
    cols = list(df.columns)
    out = ["| " + " | ".join([df.index.name or ""] + [str(c) for c in cols]) + " |",
           "|" + "---|" * (len(cols) + 1)]
    for idx, row in df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            if isinstance(v, (float, np.floating)):
                cells.append("" if np.isnan(v) else floatfmt.format(v))
            else:
                cells.append(str(v))
        out.append("| " + " | ".join([str(idx)] + cells) + " |")
    return "\n".join(out)


def style_axes(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


# ------------------------------------------------------------------
# Core per-run quantities
# ------------------------------------------------------------------
def paired_frame(ep, metric):
    """One row per (fold, side, episode): benchmark costs as columns plus one
    column per trained policy (rl_s42 ...)."""
    b = ep[ep.strategy != "rl"].pivot_table(index=["fold", "side", "episode"],
                                            columns="strategy", values=metric)
    r = ep[ep.strategy == "rl"].pivot_table(index=["fold", "side", "episode"],
                                            columns="model_seed", values=metric)
    r.columns = [f"rl_s{c}" for c in r.columns]
    keys = ep.drop_duplicates(["fold", "side", "episode"]).set_index(
        ["fold", "side", "episode"])[["ticker", "day"]]
    return b.join(r).join(keys)


def run_means(pf, bench, runs):
    """Per run (fold, seed) and side: mean benchmark cost, mean RL cost."""
    rows = []
    for fold, g in pf.groupby(level="fold"):
        for rc in runs:
            if rc not in g or g[rc].isna().all():
                continue
            for side, gs in g.groupby(level="side"):
                rows.append({"fold": fold, "seed": rc[4:], "side": side,
                             "bench": gs[bench].mean(), "rl": gs[rc].mean()})
    return pd.DataFrame(rows)


def improvement_table(pf, benches, runs, pct):
    """Mean ± std across runs of (bench - rl). pct=True gives % of bench cost."""
    out = {}
    for b in benches:
        rm = run_means(pf, b, runs)
        if pct:
            rm["v"] = (rm.bench - rm.rl) / rm.bench.abs() * 100
        else:
            rm["v"] = rm.bench - rm.rl
        row = {}
        for side in ("buy", "sell"):
            v = rm[rm.side == side]["v"]
            row[side] = f"{v.mean():+.1f} ± {v.std(ddof=1):.1f}" if len(v) > 1 else f"{v.mean():+.1f}"
        # drift-neutral: average buy and sell per run (same days, opposite drift)
        dn = rm.groupby(["fold", "seed"])["v"].mean() if not pct else \
            rm.groupby(["fold", "seed"]).apply(
                lambda g: (g.bench.mean() - g.rl.mean()) / abs(g.bench.mean()) * 100)
        row["buy+sell"] = f"{dn.mean():+.1f} ± {dn.std(ddof=1):.1f}" if len(dn) > 1 else f"{dn.mean():+.1f}"
        row["runs > 0"] = f"{int((dn > 0).sum())}/{len(dn)}"
        out[lab(b)] = row
    t = pd.DataFrame(out).T
    t.index.name = "vs"
    return t


def cluster_bootstrap(diff, clusters, n_boot, rng, alpha):
    """Mean of `diff` with a CI from resampling whole clusters."""
    df = pd.DataFrame({"d": diff, "c": clusters}).dropna()
    g = df.groupby("c")["d"].agg(["sum", "count"])
    sums, counts = g["sum"].values, g["count"].values
    k = len(g)
    idx = rng.integers(0, k, size=(n_boot, k))
    boot = sums[idx].sum(1) / counts[idx].sum(1)
    lo, hi = np.quantile(boot, [alpha / 2, 1 - alpha / 2])
    return df.d.mean(), lo, hi, k


# ------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="evaluation/batch1")
    ap.add_argument("--n-boot", type=int, default=2000)
    args = ap.parse_args()
    D = args.inp
    ep = pd.read_csv(os.path.join(D, "episodes.csv"))
    tr_path, ur_path = os.path.join(D, "traces.csv"), os.path.join(D, "urgency.csv")
    tr = pd.read_csv(tr_path) if os.path.exists(tr_path) else None
    ur = pd.read_csv(ur_path) if os.path.exists(ur_path) else None

    R = []   # report lines
    rng = np.random.default_rng(0)
    folds = [int(f) for f in sorted(ep.fold.unique())]
    n_eps = ep.groupby(["fold", "side"]).episode.nunique().min()
    R.append("# Batch 1 report\n")
    rc = os.path.join(D, "run_config.txt")
    if os.path.exists(rc):
        R.append(f"Run configuration: `{open(rc).read().strip()}`\n")
    R.append(f"Folds {folds}; {n_eps} paired episodes per fold and side; "
             f"{ep[ep.strategy == 'rl'].groupby(['fold', 'model_seed']).ngroups} trained policies. "
             f"Every strategy in an episode trades the same ticker and day.\n")

    pfs = {m: paired_frame(ep, m) for m in METRICS}
    runs = [c for c in pfs["is_bps"].columns if str(c).startswith("rl_s")]
    benches_all = [c for c in pfs["is_bps"].columns
                   if c not in runs and c not in ("ticker", "day")]

    # ---------------------------------------------------------------- 0
    R.append("## 0. Metric check: clipped vs signed cost\n")
    R.append("Mean cost in bps, averaged over all folds and both sides. The clipped "
             "metric charges adverse drift and never credits favourable drift; "
             "`drift charge` is how much of the old number that asymmetry accounts for.\n")
    rows = {}
    for s in HEADLINE + ["rl"]:
        sub = ep[ep.strategy == s]
        rows[lab(s)] = {"clipped (old)": sub.is_bps.mean(),
                        "signed IS": sub.is_signed_bps.mean(),
                        "drift charge": sub.is_bps.mean() - sub.is_signed_bps.mean(),
                        "finish step": sub.finish_step.mean(),
                        "done by 25%": sub.done_25.mean() * 100}
    t0 = pd.DataFrame(rows).T
    t0.index.name = "strategy"
    R.append(md_table(t0, "{:.1f}") + "\n")

    # ---------------------------------------------------------------- 1
    R.append(f"## 1. Headline: agent vs benchmarks, {ep[ep.strategy == 'rl'].groupby(['fold', 'model_seed']).ngroups} runs\n")
    R.append("**Old metric (clipped)**: % cost reduction, mean ± std across runs. "
             "This should reproduce the published table.\n")
    R.append(md_table(improvement_table(pfs["is_bps"], HEADLINE, runs, pct=True)) + "\n")
    R.append("**Signed implementation shortfall**: cost saved in **bps** "
             "(benchmark − agent), mean ± std across runs. Percentages are not used "
             "because signed means can sit near zero. `buy+sell` averages each run's "
             "buy and sell results; buy and sell episodes share days, so market drift "
             "cancels exactly and what remains is execution.\n")
    R.append(md_table(improvement_table(pfs["is_signed_bps"], HEADLINE, runs, pct=False)) + "\n")

    # ---------------------------------------------------------------- 2
    R.append("## 2. Benchmark sweep: is the agent better than the best setting?\n")
    sweep_rows = {}
    for s in benches_all:
        sub = ep[ep.strategy == s]
        sweep_rows[lab(s)] = {
            "clipped": sub.is_bps.mean(),
            "signed": sub.is_signed_bps.mean(),
            "signed std": sub.groupby("side").is_signed_bps.std().mean(),
            "finish step": sub.finish_step.mean(),
        }
    rl_sub = ep[ep.strategy == "rl"]
    sweep_rows["RL agent"] = {"clipped": rl_sub.is_bps.mean(),
                              "signed": rl_sub.is_signed_bps.mean(),
                              "signed std": rl_sub.groupby(["side", "fold", "model_seed"])
                              .is_signed_bps.std().mean(),
                              "finish step": rl_sub.finish_step.mean()}
    ts = pd.DataFrame(sweep_rows).T
    order = ["TWAP", "VWAP"] + [lab(s) for s in benches_all if s.startswith("ac@")] \
            + [lab(s) for s in benches_all if s.startswith("pov@")] \
            + [lab(s) for s in benches_all if s.startswith("acv@")] \
            + [lab(s) for s in benches_all if s.startswith("acl@")] \
            + [lab(s) for s in benches_all if s.startswith("acs")] + ["RL agent"]
    ts = ts.loc[[o for o in order if o in ts.index]]
    ts.index.name = "setting"
    R.append("Mean cost (bps) at every setting, all folds and sides.\n")
    R.append(md_table(ts, "{:.1f}") + "\n")

    R.append("**Agent vs the best setting of each family.** The best setting for "
             "fold *k* is chosen on the other folds (leave-one-fold-out), so it is "
             "not fitted to the episodes it is scored on. `oracle` picks on all folds "
             "including the scored one and is the most generous possible benchmark.\n")
    fam = {"AC": [s for s in benches_all if s.startswith("ac@")],
           "POV": [s for s in benches_all if s.startswith("pov@")]}
    if any(s.startswith("acl@") for s in benches_all):
        fam["AC volume clock (live)"] = [s for s in benches_all if s.startswith("acl@")]
    if any(s.startswith("acs") for s in benches_all):
        fam["AC live, spread-aware"] = [s for s in benches_all if s.startswith("acs")]
    best_rows = {}
    for metric, mname in METRICS.items():
        pf = pfs[metric]
        for fname, members in fam.items():
            fold_cost = pf.groupby(level="fold")[members].mean()
            # buy and sell pooled -> drift-neutral selection
            oracle = fold_cost.mean().idxmin()
            vals_lofo, vals_or, picks = [], [], []
            for fold in folds:
                others = fold_cost.drop(index=fold) if len(folds) > 1 else fold_cost
                pick = others.mean().idxmin()
                picks.append(pick)
                g = pf.xs(fold, level="fold")
                for rc in runs:
                    if rc in g and not g[rc].isna().all():
                        vals_lofo.append(g[pick].mean() - g[rc].mean())
                        vals_or.append(g[oracle].mean() - g[rc].mean())
            vl, vo = np.array(vals_lofo), np.array(vals_or)
            best_rows[f"{mname}: best {fname}"] = {
                "oracle pick": lab(oracle),
                "LOFO picks": ", ".join(sorted({lab(p) for p in picks})),
                "saving vs LOFO (bps)": f"{vl.mean():+.2f} ± {vl.std(ddof=1) if len(vl) > 1 else 0:.2f}",
                "saving vs oracle (bps)": f"{vo.mean():+.2f} ± {vo.std(ddof=1) if len(vo) > 1 else 0:.2f}",
                "runs > 0 (LOFO)": f"{int((vl > 0).sum())}/{len(vl)}",
            }
    tb = pd.DataFrame(best_rows).T
    tb.index.name = "comparison"
    R.append(md_table(tb) + "\n")

    # ---------------------------------------------------------------- 3
    R.append("## 3. Cost-vs-risk frontier\n")
    R.append("Signed IS. x = standard deviation of per-episode cost (risk, computed "
             "within side and averaged), y = mean cost. Down and left is better. "
             "The AC curve is the classical efficient frontier traced by risk "
             "aversion; the POV curve by participation rate. See `frontier.png`.\n")

    def frontier_points(metric):
        pts = {}
        for s in benches_all:
            sub = ep[ep.strategy == s]
            pts[s] = (sub.groupby("side")[metric].std().mean(), sub[metric].mean())
        rl_pts = [(sub.groupby("side")[metric].std().mean(), sub[metric].mean())
                  for _, sub in ep[ep.strategy == "rl"].groupby(["fold", "model_seed"])]
        rl_all = ep[ep.strategy == "rl"]
        pts["rl"] = (rl_all.groupby("side")[metric].std().mean(), rl_all[metric].mean())
        return pts, np.array(rl_pts)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), facecolor=SURFACE)
    for ax, metric in zip(axes, ["is_signed_bps", "is_bps"]):
        style_axes(ax)
        pts, rl_pts = frontier_points(metric)
        for famname, members, col in [("Almgren-Chriss", fam["AC"], C_AC),
                                      ("POV", fam["POV"], C_POV)]:
            xy = np.array([pts[m] for m in members])
            o = np.argsort(xy[:, 0])
            ax.plot(xy[o, 0], xy[o, 1], "-", color=col, lw=2, label=famname, zorder=2)
            ax.plot(xy[:, 0], xy[:, 1], "o", color=col, ms=6, mec=SURFACE, mew=1.5, zorder=3)
            for m in members:
                if m in ("ac@0.01", "ac@20", "pov@5", "pov@25"):
                    ax.annotate(lab(m).replace("AC ", ""), pts[m], textcoords="offset points",
                                xytext=(5, 4), fontsize=7, color=INK2)
        for s, col in [("twap", C_TWAP), ("vwap", C_VWAP)]:
            ax.plot(*pts[s], "s", color=col, ms=8, mec=SURFACE, mew=1.5, label=lab(s), zorder=3)
        ax.plot(rl_pts[:, 0], rl_pts[:, 1], "o", color=C_RL, ms=6, alpha=0.45, mec="none", zorder=4)
        ax.plot(*pts["rl"], "D", color=C_RL, ms=9, mec=SURFACE,
                mew=1.5, label="RL agent (pooled ◆; dots = single runs)", zorder=5)
        ax.set_xlabel("risk: std of per-episode cost (bps)", color=INK2, fontsize=9)
        ax.set_ylabel("mean cost (bps)", color=INK2, fontsize=9)
        ax.set_title("Signed implementation shortfall" if metric == "is_signed_bps"
                     else "Clipped metric (as previously reported)",
                     color=INK, fontsize=10, loc="left")
    axes[0].legend(frameon=False, fontsize=8, labelcolor=INK2, loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(D, "frontier.png"), dpi=150, facecolor=SURFACE)
    plt.close(fig)

    # dominance statement, signed
    pts, rl_pts = frontier_points("is_signed_bps")
    rx, ry = pts.pop("rl")
    dominated_by = [lab(s) for s, (x, y) in pts.items() if x <= rx and y <= ry]
    dominates = [lab(s) for s, (x, y) in pts.items() if x >= rx and y >= ry]
    R.append(f"RL agent (pooled over all runs): mean {ry:.1f} bps, risk {rx:.1f} bps. "
             f"Single runs are each scored on one fold's test period, so they scatter "
             f"with the period as well as the policy.\n")
    R.append(f"- Settings that are both cheaper AND less risky than the agent: "
             f"{', '.join(dominated_by) if dominated_by else 'none'}")
    R.append(f"- Settings the agent beats on both: "
             f"{', '.join(dominates) if dominates else 'none'}\n")

    # ---------------------------------------------------------------- 4
    R.append("## 4. Where the cost comes from (signed IS decomposition)\n")
    R.append("bps, mean over all episodes. Buy and sell are averaged, so the drift "
             "column is ~0 by construction; its per-side size is shown separately.\n")
    comp = ["drift_bps", "permanent_bps", "execution_bps", "fees_bps", "is_signed_bps"]
    rows = {}
    for s in HEADLINE + ["rl"]:
        sub = ep[ep.strategy == s]
        m = sub[comp].mean()
        rows[lab(s)] = {"drift": m.drift_bps, "own permanent": m.permanent_bps,
                        "execution": m.execution_bps, "fees": m.fees_bps,
                        "total": m.is_signed_bps,
                        "|drift| per side": sub.groupby("side").drift_bps.mean().abs().mean(),
                        "drift std": sub.groupby("side").drift_bps.std().mean()}
    t4 = pd.DataFrame(rows).T
    t4.index.name = "strategy"
    R.append(md_table(t4, "{:.2f}") + "\n")

    # ---------------------------------------------------------------- 5
    R.append("## 5. Significance: day-clustered bootstrap\n")
    n_cmp = len(HEADLINE) + len(fam)
    alpha = 0.05 / n_cmp
    R.append(f"Paired difference benchmark − agent (bps), pooled over all runs. "
             f"Episodes on the same ticker and day are correlated (same price path), "
             f"so the bootstrap resamples whole ticker-days. CI is "
             f"{(1 - alpha) * 100:.2f}% (Bonferroni over {n_cmp} comparisons). The "
             f"naive t-test treats every episode as independent and is shown for "
             f"contrast.\n")
    sig_rows = {}
    for metric, mname in METRICS.items():
        pf = pfs[metric].reset_index()
        best = {}
        for fname, members in fam.items():
            fc = pfs[metric].groupby(level="fold")[members].mean()
            best[fname] = fc.mean().idxmin()
        for b in HEADLINE + [v for v in dict.fromkeys(best.values()) if v not in HEADLINE]:
            diffs, clus = [], []
            for rc in runs:
                ok = pf[rc].notna()
                diffs.append((pf.loc[ok, b] - pf.loc[ok, rc]).values)
                clus.append((pf.loc[ok, "fold"].astype(str) + "|" + pf.loc[ok, "ticker"].astype(str)
                             + "|" + pf.loc[ok, "day"].astype(str)).values)
            d, c = np.concatenate(diffs), np.concatenate(clus)
            mean, lo, hi, k = cluster_bootstrap(d, c, args.n_boot, rng, alpha)
            naive_p = stats.ttest_1samp(d, 0).pvalue
            tag = " (best)" if b in best.values() and b not in HEADLINE else ""
            sig_rows[f"{mname}: {lab(b)}{tag}"] = {
                "mean diff": f"{mean:+.2f}", "CI": f"[{lo:+.2f}, {hi:+.2f}]",
                "excludes 0": "yes" if (lo > 0 or hi < 0) else "NO",
                "ticker-days": k, "naive p": f"{naive_p:.1e}"}
    t5 = pd.DataFrame(sig_rows).T
    t5.index.name = "comparison"
    R.append(md_table(t5) + "\n")

    # ---------------------------------------------------------------- 6
    if tr is not None and len(tr):
        R.append("## 6. What the agent does\n")
        R.append("From per-step traces. Participation = shares filled / bar volume, "
                 "only over steps where the order was still open. See `behaviour.png`.\n")
        tr["bucket"] = (tr.step // 30) * 30
        live = tr[tr.remaining_frac_before > 1e-3].copy()
        fig, axes = plt.subplots(1, 3, figsize=(13, 3.8), facecolor=SURFACE)
        # (a) participation by time of day
        ax = axes[0]; style_axes(ax)
        for s, col, name in [("rl", C_RL, "RL agent"), ("pov@20", C_POV, "POV 20%"),
                             ("twap", C_TWAP, "TWAP")]:
            g = tr[tr.strategy == s].groupby("bucket").participation.mean() * 100
            ax.plot(g.index, g.values, "-", color=col, lw=2, label=name)
        ax.set_title("Participation by time of day (%)", loc="left", fontsize=10, color=INK)
        ax.set_xlabel("minute of session", fontsize=9, color=INK2)
        ax.legend(frameon=False, fontsize=8, labelcolor=INK2)
        # (b) remaining inventory
        ax = axes[1]; style_axes(ax)
        for s, col, name in [("rl", C_RL, "RL agent"), ("pov@20", C_POV, "POV 20%"),
                             ("twap", C_TWAP, "TWAP")]:
            g = tr[tr.strategy == s].groupby("step").remaining_frac_before.mean() * 100
            ax.plot(g.index, g.values, "-", color=col, lw=2, label=name)
        ax.set_title("Order remaining (%)", loc="left", fontsize=10, color=INK)
        ax.set_xlabel("minute of session", fontsize=9, color=INK2)
        # (c) agent participation vs lagged conditions (while live)
        ax = axes[2]; style_axes(ax)
        rl_live = live[live.strategy == "rl"].copy()
        cond_rows = {}
        for feat, name in [("lag_volume_ratio", "prev-bar volume"),
                           ("lag_spread_bps", "prev-bar spread"),
                           ("price_move_bps", "price vs arrival"),
                           ("signal", "alpha signal")]:
            try:
                q = pd.qcut(rl_live[feat], 5, labels=False, duplicates="drop")
            except ValueError:
                continue
            g = rl_live.groupby(q).participation.mean() * 100
            cond_rows[name] = g
            ax.plot(g.index + 1, g.values, "-o", lw=2, ms=5, label=name,
                    color=[C_RL, C_AC, C_POV, C_VWAP][len(cond_rows) - 1])
        ax.set_title("Agent participation by condition quintile (%)", loc="left",
                     fontsize=10, color=INK)
        ax.set_xlabel("quintile (1 = lowest)", fontsize=9, color=INK2)
        ax.set_xticks([1, 2, 3, 4, 5])
        ax.legend(frameon=False, fontsize=8, labelcolor=INK2)
        fig.tight_layout()
        fig.savefig(os.path.join(D, "behaviour.png"), dpi=150, facecolor=SURFACE)
        plt.close(fig)

        tb6 = pd.DataFrame(cond_rows).T
        tb6.columns = [f"Q{int(c) + 1}" for c in tb6.columns]
        tb6.index.name = "agent participation % by quintile of"
        R.append(md_table(tb6, "{:.1f}") + "\n")
        if set(rl_live.volatile.dropna().unique()) <= {0.0, 1.0}:
            vol = rl_live.groupby("volatile").participation.mean() * 100
            R.append(f"Agent participation: calm regime {vol.get(0.0, np.nan):.1f}%, "
                     f"volatile regime {vol.get(1.0, np.nan):.1f}%. ")
        else:
            # honest_obs: slots 7 and 9 hold realised volatility and the quoted
            # spread instead of the hidden flags
            for col, name in [("volatile", "realised volatility"), ("news", "current quoted spread")]:
                try:
                    q = pd.qcut(rl_live[col], 5, labels=False, duplicates="drop")
                    g = (rl_live.groupby(q).participation.mean() * 100).round(1).tolist()
                    R.append(f"Agent participation by quintile of {name} (low to high): {g}%. ")
                except ValueError:
                    pass
        R.append(f"Mean passive fraction of its orders: {rl_live.passive_frac.mean() * 100:.1f}%.\n")
        # correlation between agent participation and POV20 on the same step
        m = tr[tr.strategy.isin(["rl", "pov@20"])].pivot_table(
            index=["fold", "side", "episode", "step"], columns=["strategy"],
            values="participation", aggfunc="mean").dropna()
        if len(m) > 10:
            R.append(f"Step-by-step correlation of agent and POV 20% participation "
                     f"(same episodes): {m.corr().iloc[0, 1]:.2f}.\n")

    # ---------------------------------------------------------------- 7
    if ur is not None and len(ur):
        R.append("## 7. Urgency conditioning (causal models)\n")
        g = ur.groupby("urgency_setting").agg(
            done_25=("done_25", "mean"), done_50=("done_50", "mean"),
            finish_step=("finish_step", "mean"), signed=("is_signed_bps", "mean"),
            clipped=("is_bps", "mean"))
        g["done_25"] *= 100
        g["done_50"] *= 100
        g.index.name = "urgency"
        g.columns = ["% done by 25%", "% done by 50%", "finish step",
                     "signed IS", "clipped"]
        R.append(md_table(g, "{:.1f}") + "\n")
        per = ur.groupby(["fold", "model_seed", "urgency_setting"]).done_25.mean().reset_index()
        rho = per.groupby(["fold", "model_seed"]).apply(
            lambda x: stats.spearmanr(x.urgency_setting, x.done_25).correlation)
        R.append(f"Policies whose completion rises monotonically with urgency "
                 f"(Spearman ρ = 1): {int((rho > 0.999).sum())}/{len(rho)}; "
                 f"median ρ {rho.median():.2f}.\n")

    with open(os.path.join(D, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(R))
    print("\n".join(R))
    print(f"\nWrote {D}/report.md, frontier.png, behaviour.png")


if __name__ == "__main__":
    main()