"""
evaluation/bench_train.py   (infrastructure: where does training time go?)

Trains PPO exactly as agent/train.py does, for a short fixed number of steps,
under different hardware settings, and measures:

  steps/s            environment steps per second for one training run
  total steps/s      summed over runs launched at the same time
  collect / update / eval
                     share of wall time spent simulating the market (rollout
                     collection), doing gradient updates, and in the
                     checkpoint-selection evaluation (single env, 20 episodes
                     every eval_freq steps)
  12 x 10M estimate  hours to train the 12 walk-forward models at that rate

Each setting is "device / n_envs / torch threads / eval on|off / K at once".
K > 1 launches K copies at the same moment (separate processes, separate
output folders) and adds up their throughput -- the honest test of "train 4
models at the same time".

Usage:
    python evaluation/bench_train.py                                  # default matrix
    python evaluation/bench_train.py --steps 60000 --config configs/stage3/fold0.yaml
    python evaluation/bench_train.py --matrix "cpu,8,6,eval,1;cuda,8,6,noeval,1;cpu,4,1,noeval,3"
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

DEFAULT_MATRIX = ";".join([
    # n_envs stays 8 everywhere: it sets PPO's rollout size, so changing it would
    # change the training itself, not just its speed.
    "cpu,8,6,eval,1",     # what training does today
    "cpu,8,6,noeval,1",   # same, without the checkpoint-selection evaluation
    "cuda,8,6,noeval,1",  # network on the GPU
    "cpu,8,1,noeval,1",   # one torch thread (needed when several runs share the CPU)
    "cpu,8,1,noeval,2",   # two runs at once
    "cpu,8,1,noeval,3",   # three at once
    "cpu,8,1,noeval,4",   # four at once
    "cpu,8,1,eval,3",     # three at once, with evaluation as in real training
])


def single(args):
    """One timed training run; prints a JSON line with the measurements."""
    import torch
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback, EvalCallback
    from stable_baselines3.common.env_util import make_vec_env
    from stable_baselines3.common.vec_env import SubprocVecEnv
    from agent.train import load_config, load_and_split_data, make_env_fn
    from simulator.data_split import train_test_split_days

    torch.set_num_threads(args.threads)
    cfg = load_config(args.config)
    tc = cfg["training"]
    train_df, test_df = load_and_split_data(cfg)
    vf = cfg["data"].get("val_frac") or 0.1
    train_df, val_df = train_test_split_days(train_df, test_frac=vf)

    t_setup = time.perf_counter()
    env = make_vec_env(make_env_fn(cfg, train_df, seed=args.seed), n_envs=args.n_envs,
                       seed=args.seed, vec_env_cls=SubprocVecEnv)
    eval_env = make_vec_env(make_env_fn(cfg, val_df, seed=args.seed + 9999), n_envs=1, seed=args.seed + 9999)
    model = PPO("MlpPolicy", env, learning_rate=tc.get("learning_rate", 3e-4), n_steps=tc.get("n_steps", 2048),
                batch_size=tc.get("batch_size", 256), n_epochs=tc.get("n_epochs", 10), gamma=tc.get("gamma", 0.99),
                ent_coef=tc.get("ent_coef", 0.01), clip_range=tc.get("clip_range", 0.2), verbose=0,
                seed=args.seed, policy_kwargs=dict(net_arch=dict(pi=[256, 256], vf=[256, 256])),
                device=args.device)
    setup_s = time.perf_counter() - t_setup

    T = dict(collect=0.0, update=0.0, eval=0.0)

    class Timer(BaseCallback):
        def _on_training_start(self):
            self.t0 = time.perf_counter(); self.t_re = None
        def _on_rollout_start(self):
            now = time.perf_counter()
            if self.t_re is not None:
                T["update"] += now - self.t_re
            self.t_rs = now
        def _on_rollout_end(self):
            now = time.perf_counter()
            T["collect"] += now - self.t_rs
            self.t_re = now
        def _on_step(self):
            return True
        def _on_training_end(self):
            now = time.perf_counter()
            if self.t_re is not None:
                T["update"] += now - self.t_re
            T["wall"] = now - self.t0

    class TimedEval(EvalCallback):
        def _on_step(self):
            t = time.perf_counter()
            r = super()._on_step()
            dt = time.perf_counter() - t
            if dt > 0.05:
                T["eval"] += dt
            return r

    cbs = [Timer()]
    if args.eval:
        out = tempfile.mkdtemp(prefix="bench_")
        cbs.append(TimedEval(eval_env, best_model_save_path=out, eval_freq=max(tc.get("eval_freq", 10000) // args.n_envs, 1),
                             n_eval_episodes=tc.get("n_eval_episodes", 20), deterministic=True, verbose=0))
    model.learn(total_timesteps=args.steps, callback=cbs, progress_bar=False)
    env.close()
    T["collect"] -= T["eval"]          # evaluation runs inside rollout collection
    steps = model.num_timesteps
    print("BENCH " + json.dumps(dict(steps=steps, setup_s=setup_s, **T)), flush=True)


def launch(spec, args):
    dev, n_envs, threads, ev, k = spec.split(",")
    cmd = [sys.executable, str(Path(__file__).resolve()), "--single", "--config", args.config, "--steps", str(args.steps),
           "--device", dev, "--n-envs", n_envs, "--threads", threads] + (["--eval"] if ev == "eval" else [])
    procs = [subprocess.Popen(cmd + ["--seed", str(100 + i)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, cwd=str(_root)) for i in range(int(k))]
    res = []
    for p in procs:
        out, err = p.communicate()
        line = [l for l in out.splitlines() if l.startswith("BENCH ")]
        if not line:
            print(f"  run failed ({spec}):\n{err[-2000:]}")
            continue
        res.append(json.loads(line[-1][6:]))
    return dict(dev=dev, n_envs=int(n_envs), threads=int(threads), eval=ev == "eval", k=int(k), runs=res)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/stage3/fold0.yaml")
    ap.add_argument("--steps", type=int, default=40_000)
    ap.add_argument("--matrix", default=DEFAULT_MATRIX)
    ap.add_argument("--out", default="evaluation/bench_report.md")
    ap.add_argument("--single", action="store_true")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--n-envs", type=int, default=8)
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--eval", action="store_true")
    ap.add_argument("--seed", type=int, default=100)
    args = ap.parse_args()
    os.chdir(_root)
    if args.single:
        return single(args)

    import torch
    print(f"CPU logical processors: {os.cpu_count()}, CUDA available: {torch.cuda.is_available()}"
          + (f" ({torch.cuda.get_device_name(0)})" if torch.cuda.is_available() else ""))
    rows = []
    for spec in [s.strip() for s in args.matrix.split(";") if s.strip()]:
        if spec.startswith("cuda") and not torch.cuda.is_available():
            print(f"skip {spec}: no CUDA")
            continue
        print(f"running {spec} ...", flush=True)
        t = time.perf_counter()
        r = launch(spec, args)
        r["elapsed"] = time.perf_counter() - t
        rows.append(r)
        if r["runs"]:
            fps = [x["steps"] / x["wall"] for x in r["runs"]]
            print(f"   per run {sum(fps)/len(fps):,.0f} steps/s, total {sum(fps):,.0f} steps/s")

    total_steps_needed = 12 * 10_000_000
    R = ["# Training throughput benchmark", "",
         f"Config `{args.config}`, {args.steps:,} steps per run, CPU logical processors {os.cpu_count()}, "
         f"CUDA {'yes' if torch.cuda.is_available() else 'no'}.", "",
         "| device | simulator workers (n_envs) | torch threads | eval | runs at once | steps/s per run | total steps/s | collect | update | eval | 12 x 10M models |",
         "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        if not r["runs"]:
            R.append(f"| {r['dev']} | {r['n_envs']} | {r['threads']} | {'on' if r['eval'] else 'off'} | {r['k']} | failed | | | | | |")
            continue
        fps = [x["steps"] / x["wall"] for x in r["runs"]]
        wall = sum(x["wall"] for x in r["runs"])
        sh = {k: sum(x[k] for x in r["runs"]) / wall for k in ("collect", "update", "eval")}
        tot = sum(fps)
        R.append(f"| {r['dev']} | {r['n_envs']} | {r['threads']} | {'on' if r['eval'] else 'off'} | {r['k']} | "
                 f"{sum(fps)/len(fps):,.0f} | {tot:,.0f} | {sh['collect']:.0%} | {sh['update']:.0%} | {sh['eval']:.0%} | "
                 f"{total_steps_needed / tot / 3600:.1f} h |")
    R += ["", "collect = simulating the market for new experience; update = PPO gradient steps; eval = the "
          "checkpoint-selection evaluation (single environment). Shares are of each run's wall time, averaged. "
          "'12 x 10M models' = hours to train all walk-forward models at the total rate (ignores start-up)."]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(R) + "\n")
    print("\n".join(R))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()