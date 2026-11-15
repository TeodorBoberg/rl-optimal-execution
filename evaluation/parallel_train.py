"""
evaluation/parallel_train.py   (infrastructure: train several models at once)

Runs a list of trainings with at most --max-parallel at the same time. Each
run gets its own folder (runs/<prefix>/f{fold}_s{seed}/), so runs can no
longer overwrite each other's best_model.zip, checkpoints or logs. When a run
finishes, its best_model.zip is copied to models/<prefix>_f{fold}_s{seed}.zip;
a run that produced no model is reported as FAILED (never silently replaced
by an old file). At the end every model's SHA-256 is printed, and duplicates
are flagged.

Usage:
    python evaluation/parallel_train.py --configs "configs/stage3/fold{fold}.yaml" --folds 0,1,2,3 --seeds 42,43,44 --prefix s3v --max-parallel 3 --n-envs 4 --torch-threads 1
    python evaluation/parallel_train.py --configs "configs/stage3_unseen/g{fold}_train.yaml" --folds 0,1,2,3 --seeds 42 --prefix s3vu --name-pattern "g{fold}_f3_s{seed}" ...
"""
import argparse
import hashlib
import shutil
import subprocess
import sys
import time
from pathlib import Path

_root = Path(__file__).resolve().parent.parent


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", required=True, help="Config path pattern with {fold}")
    ap.add_argument("--folds", default="0,1,2,3")
    ap.add_argument("--seeds", default="42,43,44")
    ap.add_argument("--prefix", required=True, help="Model name prefix, e.g. s3v")
    ap.add_argument("--name-pattern", default="f{fold}_s{seed}")
    ap.add_argument("--timesteps", type=int, default=10_000_000)
    ap.add_argument("--max-parallel", type=int, default=3)
    ap.add_argument("--n-envs", type=int, default=None, help="Simulator workers per run (default: config)")
    ap.add_argument("--torch-threads", type=int, default=1)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--eval-freq", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    jobs = []
    for f in [x.strip() for x in args.folds.split(",") if x.strip()]:
        for s in [x.strip() for x in args.seeds.split(",") if x.strip()]:
            name = f"{args.prefix}_" + args.name_pattern.format(fold=f, seed=s)
            run_dir = _root / "runs" / args.prefix / args.name_pattern.format(fold=f, seed=s)
            cmd = [sys.executable, "run.py", "--config", args.configs.format(fold=f), "--timesteps", str(args.timesteps),
                   "--train-seed", s, "--model-dir", str(run_dir / "models"), "--log-dir", str(run_dir / "logs"),
                   "--device", args.device, "--torch-threads", str(args.torch_threads), "--train-only", "--no-progress"]
            if args.n_envs:
                cmd += ["--n-envs", str(args.n_envs)]
            if args.eval_freq is not None:
                cmd += ["--eval-freq", str(args.eval_freq)]
            jobs.append(dict(name=name, dir=run_dir, cmd=cmd))

    print(f"{len(jobs)} trainings, at most {args.max_parallel} at once")
    if args.dry_run:
        for j in jobs:
            print(" ".join(j["cmd"]))
        return

    (_root / "models").mkdir(exist_ok=True)
    pending, running, done = list(jobs), [], []
    t0 = time.time()
    while pending or running:
        while pending and len(running) < args.max_parallel:
            j = pending.pop(0)
            j["dir"].mkdir(parents=True, exist_ok=True)
            stale = j["dir"] / "models" / "best_model.zip"
            if stale.exists():
                stale.unlink()                     # never let an old model stand in for a failed run
            j["log"] = open(j["dir"] / "train.log", "w")
            j["t"] = time.time()
            j["p"] = subprocess.Popen(j["cmd"], cwd=str(_root), stdout=j["log"], stderr=subprocess.STDOUT)
            running.append(j)
            print(f"[{time.strftime('%H:%M')}] start {j['name']}  (log: {j['dir'] / 'train.log'})", flush=True)
        time.sleep(5)
        for j in list(running):
            if j["p"].poll() is None:
                continue
            running.remove(j)
            j["log"].close()
            best = j["dir"] / "models" / "best_model.zip"
            dst = _root / "models" / f"{j['name']}.zip"
            mins = (time.time() - j["t"]) / 60
            if j["p"].returncode == 0 and best.exists():
                shutil.copy2(best, dst)
                j["ok"] = True
                print(f"[{time.strftime('%H:%M')}] done  {j['name']}  {mins:.0f} min -> {dst.name}", flush=True)
            else:
                j["ok"] = False
                print(f"[{time.strftime('%H:%M')}] FAILED {j['name']} (exit {j['p'].returncode}); see {j['dir'] / 'train.log'}",
                      flush=True)
            done.append(j)

    print(f"\nAll finished in {(time.time() - t0) / 3600:.1f} h")
    hashes = {}
    for j in done:
        p = _root / "models" / f"{j['name']}.zip"
        h = sha(p) if j["ok"] and p.exists() else "-"
        hashes.setdefault(h, []).append(j["name"])
        print(f"  {j['name']:<22} {'ok' if j['ok'] else 'FAILED':<7} {h}")
    dup = {h: n for h, n in hashes.items() if h != "-" and len(n) > 1}
    if dup:
        print("\nWARNING: identical models:", dup)
    if any(not j["ok"] for j in done):
        sys.exit(1)


if __name__ == "__main__":
    main()