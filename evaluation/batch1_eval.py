"""
evaluation/batch1_eval.py

One evaluation pass that produces everything Batch 1 needs, from the 12
walk-forward models that already exist. Nothing is trained.

For every fold, every test episode is run once for each benchmark setting
and once for each of that fold's trained policies, all on the same seed
(paired). Each episode records BOTH cost metrics:

    is_bps          the metric every earlier result used. Each fill's price
                    component is clipped at zero -- max(0, fill - arrival) --
                    so adverse drift is charged and favourable drift is
                    never credited.
    is_signed_bps   standard implementation shortfall, with its exact
                    decomposition into drift / own permanent impact /
                    execution / fees.

Benchmarks are swept rather than fixed, so the agent can be compared with
each benchmark at its best setting:

    Almgren-Chriss  risk aversion 0.01 ... 20
    POV             5% ... 25% of volume (25% is the simulator's cap)

It also writes per-step traces for a subset of episodes (what the agent
actually does, next to TWAP and POV 20%) and an urgency sweep for each
policy. batch1_analyze.py turns the three CSVs into tables and plots.

Usage:
    python evaluation/batch1_eval.py --workers 4
    python evaluation/batch1_eval.py --folds 3 --seeds 42 --n-episodes 50 --workers 2   # quick check
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
import yaml

AC_GRID = [0.01, 0.05, 0.2, 0.3, 0.6, 1.0, 1.5, 2.5, 5.0, 10.0, 20.0]
# Almgren-Chriss on a volume clock: expected-volume schedule (acv) and live,
# volume-scaled (acl). See ExecutionEnv.ac_volume_clock_action.
ACV_GRID = [0.01, 0.2, 0.6, 1.5, 5.0, 20.0]
ACL_GRID = [0.01, 0.05, 0.2, 0.6, 1.0, 1.5, 2.5, 5.0, 10.0, 20.0]
# Spread-aware AC on live volume: quantity x (typical spread / quoted spread)**k
ACS_K = [0.5, 1.0, 2.0]
ACS_GRID = [0.01, 0.05, 0.2, 0.6, 1.5, 5.0, 20.0]
BENCH_FILTER_ENV = "BATCH1_BENCH_PREFIXES"
NO_RL_ENV = "BATCH1_NO_RL"
POV_GRID = [5, 7.5, 10, 12.5, 15, 17.5, 20, 22.5, 25]
TRACE_BENCHMARKS = ["twap", "pov@20"]
URGENCY_LEVELS = [0.0, 0.25, 0.5, 0.75, 1.0]
EVAL_URGENCY = 0.5   # every paired episode, agent and AC alike


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


OVERRIDE_ENV = "BATCH1_CFG_OVERRIDES"
SMOOTH_ENV = "BATCH1_RL_SMOOTH"
GUARD_ENV = "BATCH1_RL_GUARD"          # "band,steps", e.g. "0.1,10"; empty = off


def rl_guard(env, on: bool):
    """Switch the schedule guardrail on for RL episodes, off for benchmarks."""
    raw = os.environ.get(GUARD_ENV, "")
    if on and raw:
        band, steps = raw.split(",")
        env.rl_guard_band, env.rl_guard_steps = float(band), int(steps)
    else:
        env.rl_guard_band = None


def rl_act_fn(model):
    """Policy wrapper for one episode. With BATCH1_RL_SMOOTH = alpha (0 < alpha
    < 1) the trade-size action is replaced by an exponential moving average,
    a_t = alpha * raw_t + (1 - alpha) * a_{t-1}, so step-to-step jitter from
    noisy observations is damped. Evaluation-only diagnostic: if smoothing
    lowers cost, the policy's own jitter is part of its gap to AC."""
    alpha = float(os.environ.get(SMOOTH_ENV, "0") or 0)
    state = {"prev": None}

    def act(obs):
        a = np.array(model.predict(obs, deterministic=True)[0], dtype=np.float32).ravel()
        if 0 < alpha < 1:
            if state["prev"] is not None:
                a[0] = alpha * a[0] + (1 - alpha) * state["prev"]
            state["prev"] = float(a[0])
        return a
    return act


def parse_overrides(items):
    """["market.permanent_impact_mode=cumulative", ...] -> list of (path, value).
    Values are parsed as YAML, so numbers and null work."""
    out = []
    for it in items or []:
        k, v = it.split("=", 1)
        out.append((k.strip(), yaml.safe_load(v)))
    return out


def set_overrides_env(items):
    """Stored in an environment variable so worker processes (spawned fresh
    on Windows) inherit them without changing every job signature."""
    os.environ[OVERRIDE_ENV] = "\n".join(items or [])


def apply_overrides(cfg):
    raw = os.environ.get(OVERRIDE_ENV, "")
    for path, val in parse_overrides([x for x in raw.split("\n") if x.strip()]):
        node = cfg
        keys = path.split(".")
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        node[keys[-1]] = val
    return cfg


def benchmark_specs():
    specs = [("twap", "twap", None), ("vwap", "vwap", None)]
    specs += [(f"ac@{ra:g}", "ac", ra) for ra in AC_GRID]
    specs += [(f"pov@{r:g}", "pov", r / 100.0) for r in POV_GRID]
    specs += [(f"acv@{ra:g}", "acv", ra) for ra in ACV_GRID]
    specs += [(f"acl@{ra:g}", "acl", ra) for ra in ACL_GRID]
    specs += [(f"acs{k:g}@{ra:g}", "acs", (ra, k)) for k in ACS_K for ra in ACS_GRID]
    keep = [x for x in os.environ.get(BENCH_FILTER_ENV, "").split(",") if x.strip()]
    if keep:
        specs = [sp for sp in specs if any(sp[0].startswith(pre) for pre in keep)]
    return specs


# ------------------------------------------------------------------
# Per-process cache: each worker loads a fold's data and models once.
# ------------------------------------------------------------------
_CACHE = {}


def _worker_init():
    import torch
    torch.set_num_threads(1)


def _fold_objects(fold, seeds, prefix):
    if fold in _CACHE:
        return _CACHE[fold]
    _CACHE.clear()   # hold one fold at a time; jobs are sorted by fold
    import contextlib, io
    from agent.env import ExecutionEnv
    from simulator.synthetic_data import load_csv_data, load_empirical_volume_profile
    from simulator.data_split import train_test_split_days
    from stable_baselines3 import PPO

    cfg = apply_overrides(load_config(f"configs/walkforward/fold{fold}.yaml"))
    data_cfg, exec_cfg = cfg["data"], cfg["execution"]
    full_df = load_csv_data(data_cfg["path"], exec_cfg["step_duration_min"])
    with contextlib.redirect_stdout(io.StringIO()):          # split prints a table per call
        _, test_df = train_test_split_days(full_df, test_frac=data_cfg.get("test_frac", 0.2))
    del full_df

    env = ExecutionEnv(cfg, data=test_df, side="buy", urgency=EVAL_URGENCY)
    models = {}
    for s in seeds:
        p = f"models/{prefix}_f{fold}_s{s}.zip"
        if os.path.exists(p):
            models[s] = PPO.load(p, device="cpu")
    profile = load_empirical_volume_profile(n_steps=env.total_steps)
    _CACHE[fold] = (cfg, env, models, profile)
    return _CACHE[fold]


# ------------------------------------------------------------------
# One episode, any strategy
# ------------------------------------------------------------------
def _bench_action(env, kind, param, profile):
    if kind == "twap":
        return env.twap_action()
    if kind == "vwap":
        return env.vwap_action(profile)
    if kind == "ac":
        return env.ac_action(risk_aversion=param)
    if kind == "pov":
        return env.pov_action(param)
    if kind == "acs":
        ra, k = param
        return env.ac_volume_clock_action(ra, profile, live=True, spread_k=k)
    if kind in ("acv", "acl"):
        return env.ac_volume_clock_action(param, profile, live=(kind == "acl"))
    raise ValueError(kind)


def run_episode(env, side, seed, act_fn, urgency=EVAL_URGENCY, trace=None):
    """Runs one episode. act_fn(obs) -> action. If `trace` is a list, one
    dict per step is appended to it."""
    env.default_side = side
    env.default_urgency = urgency       # set for EVERY strategy: pairing needs identical RNG draws
    obs, _ = env.reset(seed=seed)
    n = env.total_steps
    marks = {int(round(n * q)): q for q in (0.25, 0.5, 0.75)}
    done_at = {}
    finish_step = n
    filled_vol, bar_vol_active = 0.0, 0.0
    step = 0
    done = False
    while not done:
        action = act_fn(obs)
        obs_before = obs
        obs, _, done, _, info = env.step(action)
        q = info["filled_qty"]
        if q > 0:
            filled_vol += q
            bar_vol_active += info["bar_volume"]
        step += 1
        if step in marks:
            done_at[marks[step]] = 1.0 - env.remaining / env.total_shares
        if finish_step == n and env.remaining <= 1e-3 * env.total_shares:
            finish_step = step
        if trace is not None:
            a = np.asarray(action, dtype=float).ravel()
            trace.append({
                "step": step - 1,
                "action": float(a[0]),
                "passive_frac": float(a[1]) if a.size > 1 else 0.0,
                "participation": q / max(info["bar_volume"], 1.0),
                "remaining_frac_before": float(obs_before[0]),
                "price_move_bps": float(obs_before[2]) * 1e4,
                "lag_spread_bps": float(obs_before[3]) * 10.0,
                "lag_volume_ratio": float(obs_before[4]),
                "volatile": float(obs_before[7]),
                "news": float(obs_before[9]),
                "signal": float(obs_before[11]),
            })

    scale = env.arrival_price * env.total_shares / 1e4 + 1e-12
    return {
        "ticker": getattr(env, "ticker", None),
        "day": getattr(env, "day_idx", -1),
        "urgency": env.urgency,
        "is_bps": env.total_cost / scale,
        "is_signed_bps": env.total_cost_signed / scale,
        "drift_bps": env.cost_drift / scale,
        "permanent_bps": env.cost_permanent / scale,
        "execution_bps": env.cost_execution / scale,
        "fees_bps": env.cost_fees / scale,
        "done_25": done_at.get(0.25, np.nan),
        "done_50": done_at.get(0.5, np.nan),
        "done_75": done_at.get(0.75, np.nan),
        "finish_step": finish_step,
        "avg_participation": filled_vol / (bar_vol_active + 1e-9),
        "unfilled_frac": env.remaining / env.total_shares,
    }


# ------------------------------------------------------------------
# Jobs
# ------------------------------------------------------------------
def paired_job(job):
    fold, side, ep_lo, ep_hi, seeds, prefix, eval_seed, n_trace = job
    cfg, env, models, profile = _fold_objects(fold, seeds, prefix)
    specs = benchmark_specs()
    rows, traces = [], []

    for ep in range(ep_lo, ep_hi):
        ep_seed = eval_seed + ep
        want_trace = ep < n_trace

        rl_guard(env, False)
        for name, kind, param in specs:
            tr = [] if (want_trace and name in TRACE_BENCHMARKS) else None
            r = run_episode(env, side, ep_seed,
                            lambda o, k=kind, p=param: _bench_action(env, k, p, profile),
                            trace=tr)
            r.update(fold=fold, side=side, episode=ep, strategy=name, model_seed=-1)
            rows.append(r)
            if tr:
                for t in tr:
                    t.update(fold=fold, side=side, episode=ep, strategy=name, model_seed=-1)
                traces.extend(tr)

        rl_guard(env, True)
        for s, model in (models.items() if not os.environ.get(NO_RL_ENV) else []):
            tr = [] if want_trace else None
            r = run_episode(env, side, ep_seed,
                            rl_act_fn(model),
                            trace=tr)
            r.update(fold=fold, side=side, episode=ep, strategy="rl", model_seed=s)
            rows.append(r)
            if tr:
                for t in tr:
                    t.update(fold=fold, side=side, episode=ep, strategy="rl", model_seed=s)
                traces.extend(tr)

        rl_guard(env, False)

    return "paired", rows, traces


def urgency_job(job):
    fold, seed, side, n_eps, seeds, prefix, eval_seed = job
    cfg, env, models, profile = _fold_objects(fold, seeds, prefix)
    if seed not in models:
        return "urgency", [], []
    model = models[seed]
    rl_guard(env, True)
    rows = []
    for u in URGENCY_LEVELS:
        for ep in range(n_eps):
            r = run_episode(env, side, eval_seed + 500_000 + ep,
                            rl_act_fn(model), urgency=u)
            r.update(fold=fold, side=side, episode=ep, strategy="rl", model_seed=seed,
                     urgency_setting=u)
            rows.append(r)
    return "urgency", rows, []


def run_job(job):
    kind, payload = job
    return paired_job(payload) if kind == "paired" else urgency_job(payload)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", default="0,1,2,3")
    ap.add_argument("--seeds", default="42,43,44")
    ap.add_argument("--model-prefix", default="wf")
    ap.add_argument("--n-episodes", type=int, default=1000)
    ap.add_argument("--n-trace", type=int, default=100,
                    help="Per-step traces are written for the first N episodes.")
    ap.add_argument("--n-urgency", type=int, default=100,
                    help="Episodes per urgency level, per side, per policy. 0 skips.")
    ap.add_argument("--eval-seed", type=int, default=99999)
    ap.add_argument("--chunk", type=int, default=125,
                    help="Episodes per job. Smaller = better load balancing.")
    ap.add_argument("--workers", type=int, default=4,
                    help="Parallel processes. Each holds one fold's test data "
                         "and three models; ~1GB each is a safe guess.")
    ap.add_argument("--out", default="evaluation/batch1")
    ap.add_argument("--rl-smooth", type=float, default=0.0,
                    help="Evaluation-only EMA on the agent's trade-size action (0 = off).")
    ap.add_argument("--rl-guard", default="",
                    help="Schedule guardrail for the agent only: 'band,steps', e.g. '0.1,10'.")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                    help="Override a config value for every fold, e.g. "
                         "--set market.permanent_impact_mode=cumulative. Repeatable.")
    ap.add_argument("--bench-prefixes", default="",
                    help="Only run benchmarks whose name starts with one of these "
                         "comma-separated prefixes (e.g. 'acs').")
    ap.add_argument("--no-rl", action="store_true",
                    help="Benchmarks only; do not run the trained policies.")
    ap.add_argument("--append", action="store_true",
                    help="Add the new rows to an existing --out/episodes.csv (same "
                         "episodes, same overrides) instead of overwriting it.")
    args = ap.parse_args()
    set_overrides_env(args.set)
    if args.set:
        print("Config overrides:", ", ".join(args.set))
    os.environ[SMOOTH_ENV] = str(args.rl_smooth)
    os.environ[GUARD_ENV] = args.rl_guard
    os.environ[BENCH_FILTER_ENV] = args.bench_prefixes
    if args.no_rl:
        os.environ[NO_RL_ENV] = "1"
    mine = "overrides: " + (", ".join(args.set) if args.set else "none")
    if args.append:
        rc = os.path.join(args.out, "run_config.txt")
        if not os.path.exists(os.path.join(args.out, "episodes.csv")) or not os.path.exists(rc):
            raise SystemExit(f"--append needs {args.out}/episodes.csv and run_config.txt")
        used = open(rc).read().strip()
        if used != mine:
            raise SystemExit(f"Override mismatch with {rc}:\n  existing {used}\n  this run {mine}")

    folds = [int(x) for x in args.folds.split(",") if x.strip()]
    seeds = [int(x) for x in args.seeds.split(",") if x.strip()]

    for f in folds:
        if not os.path.exists(f"configs/walkforward/fold{f}.yaml"):
            raise SystemExit(f"Missing configs/walkforward/fold{f}.yaml")
        found = [s for s in seeds if os.path.exists(f"models/{args.model_prefix}_f{f}_s{s}.zip")]
        print(f"fold {f}: models for seeds {found}")
        if not found and not args.no_rl:
            raise SystemExit(f"No models for fold {f}")

    jobs = []
    for f in folds:
        for side in ("buy", "sell"):
            for lo in range(0, args.n_episodes, args.chunk):
                hi = min(lo + args.chunk, args.n_episodes)
                jobs.append(("paired", (f, side, lo, hi, seeds, args.model_prefix,
                                        args.eval_seed, args.n_trace)))
    if args.n_urgency > 0:
        for f in folds:
            for s in seeds:
                for side in ("buy", "sell"):
                    jobs.append(("urgency", (f, s, side, args.n_urgency, seeds,
                                             args.model_prefix, args.eval_seed)))
    # Group jobs by fold so each worker mostly reuses one fold's cached data
    jobs.sort(key=lambda j: j[1][0])

    n_bench = len(benchmark_specs())
    print(f"\n{len(jobs)} jobs, {args.workers} workers. Per paired episode: "
          f"{n_bench} benchmark settings + up to {len(seeds)} policies, both sides.")
    print(f"Episodes per fold: {args.n_episodes}   traces: first {args.n_trace}   "
          f"urgency sweep: {args.n_urgency}/level\n")

    os.makedirs(args.out, exist_ok=True)
    if not args.append:
        with open(os.path.join(args.out, "run_config.txt"), "w") as f:
            f.write(mine + "\n")
    ep_rows, tr_rows, urg_rows = [], [], []
    t0 = time.time()

    from tqdm import tqdm
    if args.workers <= 1:
        _worker_init()
        it = map(run_job, jobs)
        pool = None
    else:
        import multiprocessing as mp
        pool = mp.Pool(args.workers, initializer=_worker_init, maxtasksperchild=None)
        it = pool.imap_unordered(run_job, jobs)
    for kind, rows, traces in tqdm(it, total=len(jobs), desc="jobs"):
        if kind == "paired":
            ep_rows.extend(rows)
            tr_rows.extend(traces)
        else:
            urg_rows.extend(rows)
    if pool is not None:
        pool.close()
        pool.join()

    ep = pd.DataFrame(ep_rows)
    if args.append:
        old_ep = pd.read_csv(os.path.join(args.out, "episodes.csv"))
        dup = set(ep.strategy.unique()) & set(old_ep.strategy.unique())
        old_ep = old_ep[~old_ep.strategy.isin(dup)]    # re-running a strategy replaces it
        ep = pd.concat([old_ep, ep], ignore_index=True)
    ep.to_csv(os.path.join(args.out, "episodes.csv"), index=False)
    if tr_rows and not args.append:
        pd.DataFrame(tr_rows).to_csv(os.path.join(args.out, "traces.csv"), index=False)
    if urg_rows:
        pd.DataFrame(urg_rows).to_csv(os.path.join(args.out, "urgency.csv"), index=False)

    print(f"\nDone in {(time.time() - t0) / 60:.1f} min. Wrote to {args.out}/")
    print(f"  episodes.csv  {len(ep):,} rows")
    print(f"  traces.csv    {len(tr_rows):,} rows")
    print(f"  urgency.csv   {len(urg_rows):,} rows")

    # Pairing check: every strategy in an episode must have drawn the same day
    key = ["fold", "side", "episode"]
    n_days = ep.groupby(key)[["ticker", "day"]].nunique().max()
    ok = int(n_days["ticker"]) == 1 and int(n_days["day"]) == 1
    print(f"\nPairing check (one ticker and one day per episode across all strategies): "
          f"{'PASS' if ok else 'FAIL'}")
    print("Next: python evaluation/batch1_analyze.py")


if __name__ == "__main__":
    main()