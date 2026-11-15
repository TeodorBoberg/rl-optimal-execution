"""
evaluation/behaviour_probe.py   (STAGE 3c: what did the agent learn?)

Runs the trained agent (with the guardrail, as evaluated) and a few classical
schedules on the same test episodes and records every minute: what the
strategy could see, how much it traded, and what it paid. Then answers:

 1. WHERE does the agent save money?  Execution cost is split into
      half-spread paid  = sum(qty * spread at the fill / 2)
      impact            = execution cost - half-spread
    plus "spread capture": volume-weighted spread paid / the order's
    time-weighted average spread (below 1 = it trades more when the spread
    is narrow).
 2. WHAT does it react to?  Its trading pace relative to an even pace over
    the time left, by decile of: spread relative to the spreads seen so far
    in the order, last minute's volume vs normal, adverse price move since
    arrival, recent volatility, time of day, and how far ahead of or behind
    schedule it is.
 3. HOW MUCH of it is a simple rule?  A linear model and a depth-3 tree of
    log(pace) on those features, with R^2 -- the tree prints as readable
    rules.

Output: <out>/behaviour_report.md and <out>/behaviour_steps.parquet|csv.

Usage:
    python evaluation/behaviour_probe.py --model-prefix s3 --config-pattern "configs/stage3/fold{fold}.yaml"
    python evaluation/behaviour_probe.py --folds 3 --seeds 42 --n-episodes 20 --urgencies 0.5   (quick)
"""
import argparse
import multiprocessing as mp
import os
import sys

import numpy as np
import pandas as pd

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_root)
sys.path.insert(0, _root)

import evaluation.batch1_eval as B       # noqa: E402

FEATURES = ["rel_spread", "vol_ratio", "adverse_move_bps", "rv_ratio", "time_frac", "ahead"]
FEATURE_LABEL = {
    "rel_spread": "spread / mean spread so far in the order",
    "vol_ratio": "last minute's volume / normal",
    "adverse_move_bps": "price move against the order since arrival (bps)",
    "rv_ratio": "recent volatility / calibrated",
    "time_frac": "fraction of the day elapsed",
    "ahead": "share of order ahead of a straight-line pace",
}


def run_one(env, side, seed, act_fn, urgency, label, fold, model_seed, guard):
    """One episode with a per-minute recorder."""
    env.default_side, env.default_urgency = side, urgency
    obs, _ = env.reset(seed=seed)
    env.rl_guard_band = guard[0] if guard else None
    env.rl_guard_steps = guard[1] if guard else 10
    n, X = env.total_steps, env.total_shares
    qs_hist, rows = [], []
    done, t = False, 0
    exec_before = 0.0
    while not done:
        q_spread = float(env.quoted_spread_bps())
        qs_hist.append(q_spread)
        steps_left = n - env.step_count
        rem = env.remaining
        target_rem = X * (1.0 - env.step_count / n)
        pay_spread = float(getattr(env.sim, "last_spread_bps", q_spread) or q_spread)
        a = act_fn(obs)
        obs_before = obs
        obs, _, done, _, info = env.step(a)
        q = float(info["filled_qty"])
        d_exec = env.cost_execution - exec_before
        exec_before = env.cost_execution
        scale = env.arrival_price * X / 1e4
        rows.append(dict(
            strategy=label, fold=fold, model_seed=model_seed, urgency=urgency, side=side,
            seed=seed, step=t, time_frac=t / n,
            rel_spread=q_spread / max(np.mean(qs_hist), 1e-9),
            spread_bps=q_spread, pay_spread_bps=pay_spread,
            vol_ratio=float(obs_before[4]),
            adverse_move_bps=float(obs_before[2]) * 1e4 * (1 if side == "buy" else -1),
            rv_ratio=float(obs_before[7]) * 3.0,
            ahead=(target_rem - rem) / X,
            qty_frac=q / X, qty=q, rem_frac=rem / X, even_pace=rem / max(steps_left, 1) / X,
            bar_volume=float(info["bar_volume"]),
            half_spread_bps=q * pay_spread / 2.0 / X,
            exec_bps=d_exec / scale,
        ))
        t += 1
    return rows


def job(args):
    fold, seeds, prefix, n_eps, urgencies, eval_seed, guard, benches = args
    cfg, env, models, profile = B._fold_objects(fold, seeds, prefix)
    rows = []
    for ep in range(n_eps):
        for side in ("buy", "sell"):
            seed = eval_seed + 900_000 + ep * 2 + (side == "sell")
            for u in urgencies:
                for s, model in models.items():
                    rows += run_one(env, side, seed, B.rl_act_fn(model), u, "rl", fold, s, guard)
            # Benchmarks ignore urgency (their speed is their own parameter): run
            # once per episode, on the same seed and so the same price path.
            for name, kind, param in benches:
                g = guard if kind.startswith("g:") else None
                k = kind[2:] if kind.startswith("g:") else kind
                rows += run_one(env, side, seed,
                                lambda o, k=k, p=param: B._bench_action(env, k, p, profile),
                                urgencies[0], name, fold, -1, g)
    return rows


def episode_table(st):
    g = st.groupby(["strategy", "fold", "model_seed", "urgency", "side", "seed"])
    e = pd.DataFrame({
        "exec_bps": g.exec_bps.sum(),
        "half_spread_bps": g.half_spread_bps.sum(),
        "vw_spread": g.apply(lambda d: np.average(d.pay_spread_bps, weights=d.qty_frac + 1e-15)),
        "tw_spread": g.pay_spread_bps.mean(),
        "participation": g.apply(lambda d: d.qty.sum() / max((d.bar_volume * (d.qty > 0)).sum(), 1e-9)),
    }).reset_index()
    e["impact_bps"] = e.exec_bps - e.half_spread_bps
    e["spread_capture"] = e.vw_spread / e.tw_spread
    return e


def response_tables(st, strat):
    d = st[(st.strategy == strat) & (st.rem_frac > 0.02) & (st.time_frac < 0.98)].copy()
    d["pace"] = d.qty_frac / d.even_pace
    out = {}
    for f in FEATURES:
        try:
            d["bin"] = pd.qcut(d[f], 10, duplicates="drop")
        except ValueError:
            continue
        out[f] = d.groupby("bin", observed=True).agg(x=(f, "median"), pace=("pace", "median"),
                                                     n=("pace", "size"))
    return out


def fit_rules(st, strat):
    d = st[(st.strategy == strat) & (st.rem_frac > 0.02) & (st.time_frac < 0.98)].copy()
    y = np.log(np.clip(d.qty_frac / d.even_pace, 0.05, 20))
    X = d[FEATURES].astype(float).values
    mu, sd = X.mean(0), X.std(0) + 1e-12
    Z = (X - mu) / sd
    A = np.column_stack([np.ones(len(Z)), Z])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    r2_lin = 1 - np.var(y - A @ beta) / np.var(y)
    tree_txt, r2_tree = "", np.nan
    try:
        from sklearn.tree import DecisionTreeRegressor, export_text
        tr = DecisionTreeRegressor(max_depth=3, min_samples_leaf=max(50, len(y) // 200)).fit(X, y)
        r2_tree = tr.score(X, y)
        tree_txt = export_text(tr, feature_names=FEATURES, decimals=2)
    except Exception as e:      # sklearn missing
        tree_txt = f"(tree skipped: {e})"
    return dict(zip(["intercept"] + FEATURES, beta)), r2_lin, r2_tree, tree_txt, len(y)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", default="0,1,2,3")
    ap.add_argument("--seeds", default="42,43,44")
    ap.add_argument("--model-prefix", default="s3")
    ap.add_argument("--config-pattern", default="configs/stage3/fold{fold}.yaml")
    ap.add_argument("--urgencies", default="0.25,0.5,0.75")
    ap.add_argument("--n-episodes", type=int, default=40, help="per side, per fold")
    ap.add_argument("--rl-guard", default="0.05,10")
    ap.add_argument("--eval-seed", type=int, default=12345)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default="evaluation/behaviour")
    args = ap.parse_args()

    os.environ[B.CONFIG_ENV] = args.config_pattern
    os.environ[B.GUARD_ENV] = ""          # the probe sets the guard itself, per strategy
    band, steps = args.rl_guard.split(",")
    guard = (float(band), int(steps))
    folds = [int(x) for x in args.folds.split(",")]
    seeds = [int(x) for x in args.seeds.split(",")]
    urg = [float(x) for x in args.urgencies.split(",")]
    benches = [("twap", "twap", None), ("ac@0.05", "ac", 0.05), ("acl@0.05", "acl", 0.05),
               ("acs1@0.05", "acs", (0.05, 1.0)), ("gacs1@0.05", "g:acs", (0.05, 1.0))]

    jobs = [(f, seeds, args.model_prefix, args.n_episodes, urg, args.eval_seed, guard, benches)
            for f in folds]
    os.makedirs(args.out, exist_ok=True)
    with mp.get_context("spawn").Pool(min(args.workers, len(jobs)), initializer=B._worker_init) as pool:
        parts = pool.map(job, jobs)
    st = pd.DataFrame([r for p in parts for r in p])
    try:
        st.to_parquet(os.path.join(args.out, "behaviour_steps.parquet"))
    except Exception:
        st.to_csv(os.path.join(args.out, "behaviour_steps.csv.gz"), index=False)

    ep = episode_table(st)
    R = ["# What did the agent learn?", "",
         f"Agent `{args.model_prefix}` with guardrail {args.rl_guard}, folds {args.folds}, "
         f"seeds {args.seeds}, urgencies {args.urgencies}, {args.n_episodes} episodes per side "
         "per fold. Benchmarks run on the same episodes.", "",
         "## 1. Where the cost goes (bps of the order, mean over episodes)", "",
         "Execution = half-spread paid + impact. Spread capture = volume-weighted spread paid / "
         "time-weighted spread over the day (< 1: trades more when the spread is narrow).", "",
         "| urgency | strategy | execution | half-spread | impact | spread capture | participation |",
         "|---|---|---:|---:|---:|---:|---:|"]
    ep.loc[ep.strategy != "rl", "urgency"] = np.nan
    agg = ep.groupby(["urgency", "strategy"], dropna=False).agg(
        exec_bps=("exec_bps", "mean"), half=("half_spread_bps", "mean"),
        imp=("impact_bps", "mean"), cap=("spread_capture", "mean"),
        part=("participation", "mean")).reset_index()
    for _, r in agg.iterrows():
        ulab = "-" if pd.isna(r.urgency) else f"{r.urgency:g}"
        R.append(f"| {ulab} | {r.strategy} | {r.exec_bps:.2f} | {r.half:.2f} | "
                 f"{r.imp:.2f} | {r.cap:.3f} | {r.part:.3f} |")

    for strat in ["rl", "acs1@0.05", "gacs1@0.05"]:
        if strat not in st.strategy.unique():
            continue
        R += ["", f"## 2. What `{strat}` reacts to: pace vs an even pace over the time left, "
              "by decile of each input (all urgencies pooled)", "",
              "1.0 = trades exactly the even pace; 2.0 = twice as fast. Read across a row: if pace "
              "changes a lot from the lowest to the highest decile, the strategy reacts to that input.", ""]
        tabs = response_tables(st, strat)
        R.append("| input | " + " | ".join(f"d{i}" for i in range(1, 11)) + " |")
        R.append("|---|" + "---:|" * 10)
        for f, t in tabs.items():
            cells = [f"{p:.2f} ({x:.2g})" for x, p in zip(t.x, t.pace)]
            cells += [""] * (10 - len(cells))
            R.append(f"| {FEATURE_LABEL[f]} | " + " | ".join(cells) + " |")
        R.append("")
        R.append("Cells: median pace (median input value in that decile). Minutes after the "
                 "order is 98% done are left out.")

    R += ["", "## 3. How much of the agent is a simple rule?", ""]
    beta, r2l, r2t, tree, n = fit_rules(st, "rl")
    R += [f"log(pace) regressed on the six inputs (standardised), {n:,} agent-minutes.", "",
          "| input | coefficient (per 1 sd) |", "|---|---:|"]
    for k, v in beta.items():
        R.append(f"| {FEATURE_LABEL.get(k, k)} | {v:+.3f} |")
    R += ["", f"Linear R^2 = {r2l:.3f}; depth-3 tree R^2 = {r2t:.3f}.", "",
          "Depth-3 tree (log pace; 0 = even pace, +0.69 = twice as fast, -0.69 = half):", "",
          "```", tree, "```"]
    out = os.path.join(args.out, "behaviour_report.md")
    with open(out, "w") as f:
        f.write("\n".join(R) + "\n")
    print("\n".join(R))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()