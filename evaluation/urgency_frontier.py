"""
evaluation/urgency_frontier.py

Does the agent's urgency dial trace a better cost/risk frontier than
Almgren-Chriss's risk-aversion dial?

batch1_eval.py scored the agent at urgency 0.5 only, and found it sits ON
the AC frontier (AC at risk aversion 5 has the same mean cost with slightly
less risk). But the agent is urgency-conditioned: one policy can be asked to
be patient or urgent, just as AC can be given a different risk aversion.
The fair comparison is dial against dial.

This runs every trained policy at urgency 0, 0.25, 0.75 and 1.0 on the SAME
1,000 episodes per fold and side as batch1_eval.py (same seeds, so the same
ticker, day and price path), and merges with the benchmarks and the
urgency-0.5 results already in evaluation/batch1/episodes.csv. Nothing is
retrained and no benchmark is re-run.

Metric: signed implementation shortfall only.

For each run and each urgency level it reports the agent's mean cost minus
AC's mean cost AT THE SAME RISK, interpolated along that fold's AC curve.
Negative means the agent is below AC's frontier (better).

Usage:
    python evaluation/urgency_frontier.py --workers 6
    python evaluation/urgency_frontier.py --analyze-only
"""

import argparse
import os
import sys
import time

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
os.chdir(_root)

import numpy as np
import pandas as pd

from evaluation.batch1_eval import (_fold_objects, _worker_init, run_episode, set_overrides_env,
                                    rl_act_fn, SMOOTH_ENV, GUARD_ENV, rl_guard)

NEW_URGENCIES = [0.0, 0.25, 0.75, 1.0]      # 0.5 is already in episodes.csv
METRIC = "is_signed_bps"


def job(args):
    fold, side, lo, hi, seeds, prefix, eval_seed, urgencies = args
    cfg, env, models, profile = _fold_objects(fold, seeds, prefix)
    rl_guard(env, True)
    rows = []
    for ep in range(lo, hi):
        for s, model in models.items():
            for u in urgencies:
                r = run_episode(env, side, eval_seed + ep,
                                rl_act_fn(model),
                                urgency=u)
                r.update(fold=fold, side=side, episode=ep, strategy="rl",
                         model_seed=s, urgency_setting=u)
                rows.append(r)
    return rows


# ------------------------------------------------------------------
# Analysis
# ------------------------------------------------------------------
def risk_mean(df):
    """(risk, mean): std of per-episode cost within each side, averaged over
    sides; mean over all episodes. Buy and sell share days, so drift cancels
    in the mean."""
    return df.groupby("side")[METRIC].std().mean(), df[METRIC].mean()


# Benchmark families compared with the agent at equal risk: (prefix, label, colour)
FAMILIES = [
    ("ac@", "AC, time clock", "#eb6834"),
    ("acv@", "AC, volume clock (expected volume)", "#008300"),
    ("acl@", "AC, volume clock (live volume)", "#4a3aa7"),
    ("pov@", "POV", "#1baf7a"),
    ("acs0.5@", "AC live, spread-aware k=0.5", "#e87ba4"),
    ("acs1@", "AC live, spread-aware k=1", "#d55181"),
    ("acs2@", "AC live, spread-aware k=2", "#e34948"),
]
SPREAD_AWARE = ("acs",)


def ac_curve(df_fold, prefix="ac@"):
    pts = []
    for s, g in df_fold[df_fold.strategy.str.startswith(prefix)].groupby("strategy"):
        pts.append(risk_mean(g))
    if not pts:
        return None, None
    pts = np.array(sorted(pts))
    # Lower convex hull: the frontier the family can actually reach (any point
    # between two settings is attainable by mixing them across orders). Using
    # the raw zig-zag would let a dominated setting make the benchmark look
    # worse than it is.
    hull = []
    for p in pts:
        while len(hull) >= 2:
            (x1, y1), (x2, y2) = hull[-2], hull[-1]
            if (x2 - x1) * (p[1] - y1) - (y2 - y1) * (p[0] - x1) <= 0:
                hull.pop()
            else:
                break
        hull.append(tuple(p))
    hull = np.array(hull)
    return hull[:, 0], hull[:, 1]


def ac_cost_at_risk(xs, ys, x):
    """Benchmark mean cost at risk x, linear interpolation along the curve.
    Outside the curve's risk range np.interp clamps to the nearest endpoint,
    i.e. compares with the closest setting that was actually run, rather
    than extrapolating. Returns (cost, outside_range)."""
    return float(np.interp(x, xs, ys)), bool(x < xs.min() or x > xs.max())


def _hull_interp(xs, ys, x):
    """Lower convex hull of (xs, ys), then linear interpolation at x
    (clamped at the ends) -- same rule as ac_curve + ac_cost_at_risk."""
    o = np.argsort(xs)
    pts = np.column_stack([xs[o], ys[o]])
    hull = []
    for p in pts:
        while len(hull) >= 2:
            (x1, y1), (x2, y2) = hull[-2], hull[-1]
            if (x2 - x1) * (p[1] - y1) - (y2 - y1) * (p[0] - x1) <= 0:
                hull.pop()
            else:
                break
        hull.append(tuple(p))
    h = np.array(hull)
    return float(np.interp(x, h[:, 0], h[:, 1]))


def bootstrap_gap_best(bench, rl, families, n_boot=1000, seed=0):
    """Confidence interval for the 'best classical' gap, resampling whole
    ticker-days (episodes on the same day share a price path, so they are not
    independent). For each bootstrap draw every strategy is re-scored on the
    SAME resampled days, the families' hulls are rebuilt, and the gap is
    averaged over runs. Returns {urgency: (mean, lo, hi)} with a 95% CI."""
    rng = np.random.default_rng(seed)
    out = {}
    folds = sorted(rl.fold.unique())
    # per fold: cluster index and per-entity per-side sufficient statistics
    stats = []
    for fold in folds:
        b = bench[bench.fold == fold]
        r = rl[rl.fold == fold]
        clus = pd.Index(sorted(set(zip(b.ticker, b.day))))
        k = len(clus)

        def suff(df):
            res = {}
            for side, g in df.groupby("side"):
                ci = clus.get_indexer(list(zip(g.ticker, g.day)))
                v = g[METRIC].values
                res[side] = (np.bincount(ci, minlength=k).astype(float),
                             np.bincount(ci, weights=v, minlength=k),
                             np.bincount(ci, weights=v * v, minlength=k))
            return res
        fam_ents = {pre: {s: suff(g) for s, g in b[b.strategy.str.startswith(pre)].groupby("strategy")}
                    for pre in families}
        rl_ents = {(sd, u): suff(g) for (sd, u), g in r.groupby(["model_seed", "urgency_setting"])}
        stats.append((k, fam_ents, rl_ents))

    def score(suf, w):
        risks, n_tot, s_tot = [], 0.0, 0.0
        for side, (n, s1, s2) in suf.items():
            nn, ss, qq = w @ n, w @ s1, w @ s2
            m = ss / nn
            risks.append(np.sqrt(max(qq / nn - m * m, 0.0) * nn / max(nn - 1, 1)))
            n_tot += nn
            s_tot += ss
        return float(np.mean(risks)), s_tot / n_tot

    levels = sorted(rl.urgency_setting.unique())
    draws = {u: [] for u in levels}
    for bi in range(n_boot + 1):          # draw 0 = the original sample
        per_u = {u: [] for u in levels}
        for k, fam_ents, rl_ents in stats:
            w = np.ones(k) if bi == 0 else rng.multinomial(k, np.ones(k) / k).astype(float)
            curves = {}
            for pre, ents in fam_ents.items():
                pts = np.array([score(sf, w) for sf in ents.values()])
                curves[pre] = pts
            for (sd, u), sf in rl_ents.items():
                x, y = score(sf, w)
                best = min(_hull_interp(c[:, 0], c[:, 1], x) for c in curves.values())
                per_u[u].append(y - best)
        for u in levels:
            draws[u].append(np.mean(per_u[u]))
    for u in levels:
        d = np.array(draws[u])
        out[u] = (d[0], np.quantile(d[1:], 0.025), np.quantile(d[1:], 0.975))
    return out


def analyze(out_dir, n_boot=1000):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ep = pd.read_csv(os.path.join(out_dir, "episodes.csv"))
    ru = pd.read_csv(os.path.join(out_dir, "rl_urgency_paired.csv"))

    # Pairing check against the benchmark episodes
    key = ["fold", "side", "episode"]
    ref = ep.drop_duplicates(key).set_index(key)[["ticker", "day"]]
    chk = ru.set_index(key)[["ticker", "day"]].join(ref, rsuffix="_ref")
    paired_ok = bool(((chk.ticker == chk.ticker_ref) & (chk.day == chk.day_ref)).all())

    if 0.5 in set(ru.urgency_setting.round(6)):
        # Urgency 0.5 was re-run here (e.g. with --rl-smooth); don't mix in the
        # original agent rows from episodes.csv.
        rl = ru.copy()
    else:
        rl05 = ep[ep.strategy == "rl"].copy()
        rl05["urgency_setting"] = 0.5
        rl = pd.concat([ru, rl05], ignore_index=True)
    bench = ep[ep.strategy != "rl"]
    levels = sorted(rl.urgency_setting.unique())

    rc = os.path.join(out_dir, "run_config.txt")
    R = ["# RL urgency frontier vs Almgren-Chriss\n",
         f"Run configuration: `{open(rc).read().strip() if os.path.exists(rc) else 'unknown'}`\n",
         f"Pairing with the benchmark episodes: {'PASS' if paired_ok else 'FAIL'}. "
         f"Signed implementation shortfall. Risk = std of per-episode cost within "
         f"side, averaged over sides.\n"]

    # --- pooled points
    R.append("## Pooled over all folds and runs\n")
    R.append("| strategy | risk (bps) | mean cost (bps) | finish step | done by 25% |")
    R.append("|---|---|---|---|---|")
    pooled = {}
    for u in levels:
        g = rl[rl.urgency_setting == u]
        x, y = risk_mean(g)
        pooled[f"RL u={u:g}"] = (x, y)
        R.append(f"| RL urgency {u:g} | {x:.1f} | {y:.2f} | {g.finish_step.mean():.0f} | "
                 f"{g.done_25.mean() * 100:.0f}% |")
    fam_present = [f for f in FAMILIES if any(x.startswith(f[0]) for x in bench.strategy.unique())]
    order = ["twap", "vwap"]
    for pre, _, _ in fam_present:
        order += sorted([x for x in bench.strategy.unique() if x.startswith(pre)],
                        key=lambda x: float(x.split("@")[1]))
    for s in order:
        g = bench[bench.strategy == s]
        x, y = risk_mean(g)
        pooled[s] = (x, y)
        R.append(f"| {s} | {x:.1f} | {y:.2f} | {g.finish_step.mean():.0f} | "
                 f"{g.done_25.mean() * 100:.0f}% |")
    R.append("")

    # --- per run: distance to each benchmark frontier at equal risk
    R.append("## Agent vs each benchmark family at equal risk, per run\n")
    R.append("Agent mean cost minus the family's mean cost at the same risk, "
             "interpolated along the lower convex hull of that fold's curve (same "
             "episodes), so a dominated setting cannot flatter the agent. **Negative = "
             "agent is below that frontier, i.e. better.** Mean ± std across runs, "
             "with the number of runs below. A `*` means at least one run's risk lay "
             "outside the family's range and was compared with its nearest setting. "
             "`best classical` uses, at each risk, the cheapest of all families; "
             "`best schedule` the cheapest excluding the spread-aware ones.\n")
    hdr = ("| urgency | " + " | ".join(lab for _, lab, _ in fam_present)
           + " | best schedule | best classical |")
    R.append(hdr)
    R.append("|---|" + "---|" * (len(fam_present) + 2))
    per_run = []
    for fold in sorted(rl.fold.unique()):
        bf = bench[bench.fold == fold]
        curves = {pre: ac_curve(bf, pre) for pre, _, _ in fam_present}
        for (sd, u), g in rl[rl.fold == fold].groupby(["model_seed", "urgency_setting"]):
            x, y = risk_mean(g)
            row = {"fold": fold, "seed": sd, "urgency": u, "risk": x, "mean": y}
            best = np.inf
            for pre, _, _ in fam_present:
                xs, ys = curves[pre]
                c, o = ac_cost_at_risk(xs, ys, x)
                key = pre.rstrip("@")
                row[f"gap_{key}"] = y - c
                row[f"out_{key}"] = o
                best = min(best, c)
            row["gap_best"] = y - best
            sched = [row[f"gap_{pre.rstrip('@')}"] for pre, _, _ in fam_present
                     if not pre.startswith(SPREAD_AWARE)]
            row["gap_best_sched"] = max(sched) if sched else np.nan
            per_run.append(row)
    pr = pd.DataFrame(per_run)
    pr.to_csv(os.path.join(out_dir, "urgency_frontier_runs.csv"), index=False)
    for u, g in pr.groupby("urgency"):
        cells = []
        for pre, _, _ in fam_present + [("best_sched@", None, None), ("best@", None, None)]:
            key = pre.rstrip("@")
            v = g[f"gap_{key}"].dropna()
            sd = v.std(ddof=1) if len(v) > 1 else 0.0
            star = "*" if not key.startswith("best") and g[f"out_{key}"].any() else ""
            cells.append(f"{v.mean():+.2f} ± {sd:.2f} ({int((v < 0).sum())}/{len(v)}){star}")
        R.append(f"| {u:g} | " + " | ".join(cells) + " |")
    R.append("")

    if n_boot > 0:
        R.append("### Is the best-classical gap more than sampling noise?\n")
        R.append(f"95% interval for the `best classical` gap (averaged over runs), from "
                 f"{n_boot} bootstrap draws that resample whole ticker-days and re-score "
                 f"every strategy, rebuild every hull and recompute every gap on the same "
                 f"draw. The ± in the table above is only the spread across training "
                 f"seeds; this is the uncertainty from which days happened to be sampled.\n")
        all_pre = [pre for pre, _, _ in fam_present]
        sched_pre = [p for p in all_pre if not p.startswith(SPREAD_AWARE)]
        sets = [("best schedule", sched_pre)]
        if len(sched_pre) < len(all_pre):
            sets.append(("best classical incl. spread-aware", all_pre))
        R.append("| urgency | compared with | gap (bps) | 95% interval | excludes 0 |")
        R.append("|---|---|---|---|---|")
        res = {name: bootstrap_gap_best(bench, rl, pres, n_boot=n_boot) for name, pres in sets}
        for u in sorted(rl.urgency_setting.unique()):
            for name, _ in sets:
                m, lo, hi = res[name][u]
                R.append(f"| {u:g} | {name} | {m:+.2f} | [{lo:+.2f}, {hi:+.2f}] | "
                         f"{'yes' if (lo > 0 or hi < 0) else 'NO'} |")
        R.append("")

    # --- plot
    C_RL, C_AC, C_POV, C_TWAP, C_VWAP = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
    INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e6e5e0", "#fcfcfb"
    fig, ax = plt.subplots(figsize=(7.5, 5), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(MUTED)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)

    def curve(prefix, col, name, key, by_risk=True):
        ks = sorted([k for k in pooled if k.startswith(prefix)], key=key)
        xy = np.array([pooled[k] for k in ks])
        o = np.argsort(xy[:, 0]) if by_risk else np.arange(len(ks))
        ax.plot(xy[o, 0], xy[o, 1], "-", color=col, lw=2, label=name, zorder=2)
        ax.plot(xy[:, 0], xy[:, 1], "o", color=col, ms=6, mec=SURFACE, mew=1.5, zorder=3)
        return ks, xy

    for pre, lab_, col in fam_present:
        curve(pre, col, lab_, lambda k: float(k.split("@")[1]))
    ks, xy = curve("RL u=", C_RL, "RL agent (urgency 0 → 1)", lambda k: float(k[5:]),
                   by_risk=False)
    for k, (x, y) in zip(ks, xy):
        ax.annotate(f"u={k[5:]}", (x, y), textcoords="offset points", xytext=(6, -10),
                    fontsize=7, color=INK2)
    ax.plot(*pooled["twap"], "s", color=C_TWAP, ms=8, mec=SURFACE, mew=1.5, label="TWAP")
    ax.plot(*pooled["vwap"], "s", color=C_VWAP, ms=8, mec=SURFACE, mew=1.5, label="VWAP")
    ax.set_xlabel("risk: std of per-episode cost (bps)", color=INK2, fontsize=9)
    ax.set_ylabel("mean cost, signed IS (bps)", color=INK2, fontsize=9)
    ax.set_title("Cost/risk frontier: RL urgency dial vs classical strategies",
                 color=INK, fontsize=10, loc="left")
    # POV 5% sits far above everything else; keep the frontier region readable
    ys = [v[1] for k, v in pooled.items() if k not in ("pov@5", "pov@7.5")]
    ax.set_ylim(min(ys) - 1, max(ys) + 1.5)
    ax.legend(frameon=False, fontsize=8, labelcolor=INK2, loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "frontier_urgency.png"), dpi=150, facecolor=SURFACE)
    plt.close(fig)
    R.append("POV 5% and 7.5% may be off the top of the plot (it cannot finish orders of 5% ADV "
             "cleanly). See `frontier_urgency.png`.\n")

    txt = "\n".join(R)
    with open(os.path.join(out_dir, "urgency_frontier.md"), "w", encoding="utf-8") as f:
        f.write(txt)
    print(txt)
    print(f"\nWrote {out_dir}/urgency_frontier.md, frontier_urgency.png, urgency_frontier_runs.csv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", default="0,1,2,3")
    ap.add_argument("--seeds", default="42,43,44")
    ap.add_argument("--model-prefix", default="wf")
    ap.add_argument("--n-episodes", type=int, default=1000,
                    help="Must not exceed what batch1_eval.py ran.")
    ap.add_argument("--eval-seed", type=int, default=99999,
                    help="Must match batch1_eval.py so the episodes are the same.")
    ap.add_argument("--chunk", type=int, default=125)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default="evaluation/batch1")
    ap.add_argument("--analyze-only", action="store_true")
    ap.add_argument("--n-boot", type=int, default=1000,
                    help="Bootstrap draws for the best-classical gap interval (0 = skip).")
    ap.add_argument("--urgencies", default=None,
                    help="Comma list to run instead of 0,0.25,0.75,1. Include 0.5 to re-run "
                         "the agent at 0.5 too (needed with --rl-smooth); the benchmarks "
                         "are still taken from episodes.csv.")
    ap.add_argument("--rl-smooth", type=float, default=0.0,
                    help="Evaluation-only EMA on the agent's trade-size action (0 = off).")
    ap.add_argument("--rl-guard", default="",
                    help="Schedule guardrail for the agent only: 'band,steps', e.g. '0.1,10'. "
                         "Requires --urgencies including 0.5 so the agent is fully re-run.")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                    help="Config overrides; must match the ones batch1_eval.py used "
                         "for the same --out directory.")
    args = ap.parse_args()
    set_overrides_env(args.set)
    os.environ[SMOOTH_ENV] = str(args.rl_smooth)
    os.environ[GUARD_ENV] = args.rl_guard
    urgencies = ([float(x) for x in args.urgencies.split(",") if x.strip()]
                 if args.urgencies else NEW_URGENCIES)
    cfg_note = os.path.join(args.out, "run_config.txt")
    if os.path.exists(cfg_note) and not args.analyze_only:
        used = open(cfg_note).read().strip()
        mine = "overrides: " + (", ".join(args.set) if args.set else "none")
        if used != mine:
            raise SystemExit(f"Override mismatch with {cfg_note}:\n  batch1_eval used  {used}\n"
                             f"  this run          {mine}\nThe episodes would not be comparable.")

    if not os.path.exists(os.path.join(args.out, "episodes.csv")):
        raise SystemExit(f"{args.out}/episodes.csv not found -- run batch1_eval.py first.")

    if not args.analyze_only:
        folds = [int(x) for x in args.folds.split(",") if x.strip()]
        seeds = [int(x) for x in args.seeds.split(",") if x.strip()]
        jobs = [(f, side, lo, min(lo + args.chunk, args.n_episodes), seeds,
                 args.model_prefix, args.eval_seed, urgencies)
                for f in folds for side in ("buy", "sell")
                for lo in range(0, args.n_episodes, args.chunk)]
        print(f"{len(jobs)} jobs, {args.workers} workers; urgencies {urgencies}, "
              f"rl_smooth {args.rl_smooth}; "
              f"x {len(seeds)} policies x {args.n_episodes} episodes x 2 sides x {len(folds)} folds")
        t0 = time.time()
        rows = []
        from tqdm import tqdm
        if args.workers <= 1:
            _worker_init()
            for r in tqdm(map(job, jobs), total=len(jobs), desc="jobs"):
                rows.extend(r)
        else:
            import multiprocessing as mp
            with mp.Pool(args.workers, initializer=_worker_init) as pool:
                for r in tqdm(pool.imap_unordered(job, jobs), total=len(jobs), desc="jobs"):
                    rows.extend(r)
        pd.DataFrame(rows).to_csv(os.path.join(args.out, "rl_urgency_paired.csv"), index=False)
        print(f"Done in {(time.time() - t0) / 60:.1f} min, {len(rows):,} episodes.\n")

    analyze(args.out, n_boot=args.n_boot)


if __name__ == "__main__":
    main()