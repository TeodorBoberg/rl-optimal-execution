"""
evaluation/make_stage1_configs.py

Writes configs/stage1/fold{k}.yaml from configs/walkforward/fold{k}.yaml
with the Stage 1 changes. Stage 1 asks: on a simulator whose optimum is
known (the Almgren-Chriss frontier), does an agent trained on the ACTUAL
objective reach it?

Changes, and why:
  market.permanent_impact_mode = cumulative
      permanent impact depends on how much of the order has executed, not
      on the number of fills (the per-fill form produced every earlier edge)
  execution.reward_mode = mean_variance
      reward = -(execution + permanent + fees) - lambda(urgency) * risk,
      i.e. the Almgren-Chriss objective, instead of eight shaping terms
  reward_weights.disable_alpha_signal = true
      the synthetic alpha signal is built from future returns; with it the
      static AC schedule is no longer the optimum, so the test would lose its
      known answer. (Its ablation already showed no effect.)
  training.gamma = 0.999
      the objective is the undiscounted episode total. With gamma 0.99 the
      forced liquidation at step 390 is worth 0.99**390 = 2% of its cost when
      seen from the open, so early decisions barely feel it.
  data.val_frac = 0.1
      the best checkpoint is picked on the last 10% of the TRAINING window,
      not on the test window (needs the train.py change)
  execution.drawdown_stop_frac = null

Usage:
    python evaluation/make_stage1_configs.py
    python evaluation/make_stage1_configs.py 3 --no-passive     # -> configs/stage1_np/fold3.yaml
    python evaluation/make_stage1_configs.py 3 --no-passive --clock-rate   # -> configs/stage1_np_clk/
    python evaluation/make_stage1_configs.py 3 --no-passive --squash       # -> configs/stage1_np_sq/
    python evaluation/make_stage1_configs.py 3 --no-passive --squash --impact-bar              # -> configs/stage2_np_sq/
    python evaluation/make_stage1_configs.py 3 --no-passive --squash --impact-bar --adv-rate   # -> configs/stage2_np_adv_sq/
"""
import copy
import os
import sys
import yaml

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_root)

CHANGES = {
    ("market", "permanent_impact_mode"): "cumulative",
    ("execution", "reward_mode"): "mean_variance",
    ("execution", "drawdown_stop_frac"): None,
    ("reward_weights", "disable_alpha_signal"): True,
    ("training", "gamma"): 0.999,
    ("data", "val_frac"): 0.1,
}

import argparse
ap = argparse.ArgumentParser()
ap.add_argument("folds", nargs="?", default="0,1,2,3")
ap.add_argument("--no-passive", action="store_true",
                help="Aggressive orders only (execution.enable_passive = false), so the "
                     "agent has the same order types as the benchmarks. Written to "
                     "configs/stage1_np/ unless --out-dir is given.")
ap.add_argument("--clock-rate", action="store_true",
                help="execution.action_mode = clock_rate: the action is a multiple of "
                     "the TWAP pace (log scale) instead of a share of the bar's volume.")
ap.add_argument("--squash", action="store_true",
                help="execution.action_squash = sigmoid and execution.drop_noise_obs = true: "
                     "no hard clip at 0 in the operating range, and the generated-noise "
                     "book_imbalance input zeroed.")
ap.add_argument("--smooth-penalty", type=float, default=0.0,
                help="execution.action_change_penalty (0 = off).")
ap.add_argument("--impact-bar", action="store_true",
                help="STAGE 2: market.impact_volume_ref = bar -- temporary impact measured "
                     "against this minute's actual volume. Configs go to configs/stage2*/.")
ap.add_argument("--adv-rate", action="store_true",
                help="execution.action_mode = adv_rate: linear rate against AVERAGE minute "
                     "volume (smooth clock-time schedule when constant).")
ap.add_argument("--honest-obs", action="store_true",
                help="execution.honest_obs = true: the true regime and news flags are "
                     "replaced by realised volatility and the current quoted spread.")
ap.add_argument("--out-dir", default=None)
args = ap.parse_args()
tag = "stage2" if args.impact_bar else "stage1"
if args.impact_bar:
    CHANGES[("market", "impact_volume_ref")] = "bar"
if args.adv_rate:
    CHANGES[("execution", "action_mode")] = "adv_rate"
if args.no_passive:
    CHANGES[("execution", "enable_passive")] = False
    tag += "_np"
if args.clock_rate:
    CHANGES[("execution", "action_mode")] = "clock_rate"
    tag += "_clk"
if args.adv_rate:
    tag += "_adv"
if args.squash:
    CHANGES[("execution", "action_squash")] = "sigmoid"
    CHANGES[("execution", "drop_noise_obs")] = True
    tag += "_sq"
if args.honest_obs:
    CHANGES[("execution", "honest_obs")] = True
    tag += "_ho"
if args.smooth_penalty > 0:
    CHANGES[("execution", "action_change_penalty")] = args.smooth_penalty
    tag += f"_sp{args.smooth_penalty:g}".replace(".", "")
out_dir = args.out_dir or f"configs/{tag}"
os.makedirs(out_dir, exist_ok=True)
folds = [int(x) for x in args.folds.split(",") if x.strip()]
for k in folds:
    src = f"configs/walkforward/fold{k}.yaml"
    with open(src) as f:
        cfg = yaml.safe_load(f)
    out = copy.deepcopy(cfg)
    for (sec, key), val in CHANGES.items():
        out.setdefault(sec, {})
        if out[sec] is None:
            out[sec] = {}
        out[sec][key] = val
    dst = f"{out_dir}/fold{k}.yaml"
    with open(dst, "w") as f:
        yaml.safe_dump(out, f, sort_keys=False)
    print(f"wrote {dst}")
print("\nChanged keys:")
for (sec, key), val in CHANGES.items():
    print(f"  {sec}.{key} = {val}")