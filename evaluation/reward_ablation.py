"""
evaluation/reward_ablation.py

Sets up reward-term ablations: for each term, a config with that term's
weight zeroed, then train and evaluate to see whether it matters.

Why: seven of the eight reward terms have never been tested. They were
hand-tuned reactively while debugging other problems, and their weights
have carried forward unexamined ever since. The one term that HAS been
ablated (alpha) turned out not to matter -- removing the synthetic
forecasting signal from both reward and observation changed results by
under 2.5pp. That is exactly the kind of thing worth knowing about the
others.

Terms (weights are multipliers, 1.0 = current behaviour):
    trade              reward per unit traded, urgency-scaled
    impact             penalty on realised slippage
    adverse_selection  penalty on adverse selection
    hold               penalty for holding inventory, urgency-scaled
    regime             penalty for trading in a volatile regime
    news               penalty for trading in a news window
    pacing             penalty for deviating from an urgency-dependent
                       target schedule
    alpha              reward for holding into a favourable forward move
                       (already tested; included for completeness)

IMPORTANT: interpret against training-seed variance, not against zero.
Seed std is 1.6-7.7pp, so a term whose removal moves results by 3pp has
NOT been shown to matter. Only differences clearly exceeding that range
are informative from a single run each. Ablations that look significant
should be repeated across seeds before being believed.

Some terms cannot be removed without breaking the episode -- zeroing
`trade` leaves no incentive to trade at all, so the policy will simply
hold to the forced final-step liquidation. That is an expected, valid
result showing the term is load-bearing, not a bug.

Usage:
    python evaluation/reward_ablation.py
    python evaluation/reward_ablation.py --terms impact,pacing,regime --timesteps 10000000
"""

import sys
import os
import argparse
import copy
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
os.chdir(_root)

import yaml

ALL_TERMS = ["trade", "impact", "adverse_selection", "hold",
             "regime", "news", "pacing", "alpha"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--terms", default=",".join(ALL_TERMS))
    parser.add_argument("--timesteps", type=int, default=10_000_000)
    parser.add_argument("--n-runs", type=int, default=3)
    parser.add_argument("--n-episodes", type=int, default=1000)
    parser.add_argument("--output-dir", default="configs/ablation")
    args = parser.parse_args()

    base = yaml.safe_load(open(args.config))
    terms = [t.strip() for t in args.terms.split(",") if t.strip()]
    unknown = [t for t in terms if t not in ALL_TERMS]
    if unknown:
        raise SystemExit(f"Unknown term(s): {unknown}. Valid: {ALL_TERMS}")

    os.makedirs(args.output_dir, exist_ok=True)
    lines = []

    for t in terms:
        cfg = copy.deepcopy(base)
        rw = cfg.setdefault("reward_weights", {})
        rw[t] = 0.0
        # Alpha needs the observation zeroed too, otherwise the policy can
        # still condition on the signal and the ablation measures nothing.
        if t == "alpha":
            rw["disable_alpha_signal"] = True

        path = os.path.join(args.output_dir, f"no_{t}.yaml").replace("\\", "/")
        with open(path, "w") as f:
            yaml.safe_dump(cfg, f, sort_keys=False)

        lines.append(
            f"REM ---- ablate: {t} ----\n"
            f"python run.py --config {path} --timesteps {args.timesteps}\n"
            f"copy models\\best_model.zip models\\ablate_no_{t}.zip\n"
            f"python evaluation\\backtest_repeated_parallel.py --config {path} "
            f"--model-path models\\ablate_no_{t}.zip "
            f"--n-runs {args.n_runs} --n-episodes {args.n_episodes}"
        )
        print(f"  {path}")

    script = os.path.join(args.output_dir, "run_ablations.txt")
    with open(script, "w") as f:
        f.write("\n\n".join(lines) + "\n")

    hours = len(terms) * (args.timesteps / 10_000_000 * 1.6 + 0.3)
    print(f"\n{len(terms)} ablation(s) written to {args.output_dir}/")
    print(f"Commands in {script}")
    print(f"Estimated ~{hours:.1f}h total "
          f"({args.timesteps/1e6:.0f}M timesteps + evaluation per term)")
    print("\nBaseline for comparison (3-seed means, concave permanent impact):")
    print("  BUY  vs TWAP +28.5% | VWAP +30.1% | AC +30.6% | POV20 -5.8%")
    print("  SELL vs TWAP +28.4% | VWAP +26.2% | AC +29.0% | POV20 +0.3%")
    print("\nA term matters only if removing it moves results well beyond the")
    print("1.6-7.7pp training-seed standard deviation.")


if __name__ == "__main__":
    main()