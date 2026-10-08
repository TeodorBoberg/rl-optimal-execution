# RL Execution System — Audit v9

Supersedes v8 and every earlier version. **The headline results in v1–v8,
including the published post, are withdrawn.** They were produced by a cost
metric that charged adverse price moves but never credited favourable ones,
and by a market model that charged permanent impact per fill rather than per
order. This document records what was wrong, how each problem was found and
fixed, what the result is once all of them are fixed, and what remains open.

---

## 1. The result

13 US large-cap tickers, 488 trading days (Aug 2024 – Jul 2026), 1-minute
bars, orders of 5% of each ticker's ADV. **4 walk-forward periods × 3
independently trained policies = 12 runs**, each evaluated on 400 paired
episodes per side from its own unseen test window. Every strategy in an
episode trades the same ticker, day and price path.

Cost is **signed implementation shortfall** in bps. Because the agent has an
urgency input that trades cost against risk, it is compared with each
classical strategy **at the same risk**: the agent's mean cost minus the
benchmark family's mean cost at equal standard deviation of cost, read off
the lower convex hull of that family's settings.

| Urgency | vs best classical (incl. spread-aware) | vs best pure schedule | vs AC, time clock | vs POV |
|---|---|---|---|---|
| 0 | −0.04 [−0.12, +0.04] | **−0.18** [−0.25, −0.09] | −0.22 (11/12) | −3.78 (12/12) |
| 0.25 | −0.11 [−0.19, −0.04] | **−0.25** [−0.32, −0.17] | −0.41 (12/12) | −2.30 (12/12) |
| 0.5 | −0.08 [−0.16, −0.00] | **−0.21** [−0.28, −0.13] | −0.52 (12/12) | −1.01 (12/12) |
| 0.75 | −0.01 [−0.09, +0.07] | **−0.11** [−0.19, −0.03] | −0.56 (12/12) | −0.57 (12/12) |
| 1 | +0.07 [−0.02, +0.16] | +0.01 [−0.07, +0.09] | −0.50 (12/12) | −0.53 (12/12) |

Negative = agent cheaper. Brackets: 95% interval from 1,000 bootstrap draws
resampling whole ticker-days (episodes on the same day share a price path),
with every hull rebuilt on each draw. Parentheses: runs (of 12) in which the
agent was cheaper. Configuration: honest observations, 5% schedule guardrail
(§4.7).

**In words.** Trained from scratch, with only information a real trader has,
the agent learns a cost/risk dial that **matches the strongest classical
strategy tested** — Almgren-Chriss on a live volume clock with a
spread-aware rule — and **beats every schedule that ignores the quoted
spread by 0.1–0.25 bps** at urgency 0–0.75. Against plain time-clock AC and
fixed-rate POV it is cheaper in essentially every run.

The magnitudes are small. Mean cost is ~8.5–9.5 bps and the per-order
standard deviation is ~95–120 bps; the differences that matter here are
tenths of a basis point. That is realistic for execution and is why the
evaluation needed paired episodes, multiple periods and clustered intervals.

**What the agent does** (traces, urgency 0.5, before the guardrail): it
front-loads — about 55% of the order is done by the quarter mark, against
25% for TWAP — and then tapers smoothly. Its participation falls from 10.4%
of a minute's volume in the quietest quintile to 7.1% in the busiest, so it
trades more in busy minutes but less than proportionally. Its
minute-to-minute participation is correlated 0.55 with POV 20%: it follows
volume, but not mechanically.

---

## 2. Withdrawn claims

| Published / earlier claim | Status | Reason |
|---|---|---|
| ~27% cheaper than TWAP/VWAP | **Withdrawn** | Clipped cost metric (§3.1) and per-fill permanent impact (§3.2) |
| ~30% cheaper than Almgren-Chriss (v1–v7) | **Withdrawn** | AC was implemented as TWAP (v8), then the two issues above |
| +11–12% vs Almgren-Chriss (v8) | **Withdrawn** | Same two issues |
| Loses to POV 20% | Reversed | The clipped metric penalised slower strategies; under signed IS the agent beats every POV rate |
| Training-seed std 0.8–1.4 pts (v8) | Superseded | Seed effects now reported per urgency level; one policy in twelve fails at low urgency without the guardrail |

The clipped metric reproduced the published table exactly when re-run on the
same models (+27.2% buy vs TWAP), which is how its effect was confirmed.

---

## 3. What was wrong with the measurement and the market model

Each item: what was wrong, how it was found, the fix, and the measured
effect.

### 3.1 The cost metric charged bad luck and ignored good luck
Each fill's price component was `max(0, fill − arrival)`. A fill below
arrival (for a buy) earned nothing, so random drift was charged when it went
against the order and never credited when it went for it. The expected
charge grows with time in the market, so it penalised slow strategies
regardless of execution quality.

- **Found:** a zero-impact toy at 4 bps/min volatility charged TWAP ~21 bps
  and a 100-minute schedule ~10 bps from drift alone — the same size as the
  reported edge.
- **Fix:** signed implementation shortfall, decomposed exactly into drift,
  own permanent impact, execution and fees.
- **Effect:** TWAP 52.8 → 11.9 bps; agent 39.2 → 8.0 bps. Edge vs TWAP
  13.7 → 4.0 bps. Against POV 20% the sign flipped from a loss to a win.

### 3.2 Permanent impact was charged per fill, not per order
Permanent impact was `γ · participation^0.18` applied to every fill. With an
exponent that concave, a tiny fill moves the price almost as much as a large
one, so total permanent cost grew with the *number* of fills. TWAP's 390
small fills paid 8.7 bps of permanent impact; the agent's bursts paid 2.3.

- **Found:** the cost decomposition showed the agent's whole edge over TWAP
  was permanent impact, while it was *more* expensive on spread and
  temporary impact.
- **Fix:** cumulative permanent impact — the price displacement depends on
  how much of the order has executed, G(X) = g·(X / 5% ADV)^0.5 (square-root
  law), and each fill pays the average of G over its own slice. Total
  permanent cost is then identical for every schedule that completes the
  order, so its unmeasurable level cannot affect any comparison.
- **Effect:** the agent's 5.6 bps lead at the patient end disappeared; TWAP
  became the cheapest strategy on average, as theory predicts.

### 3.3 Almgren-Chriss was TWAP (v8)
`risk_aversion` 1e-6…1e-2 made κ so small the AC schedule was linear.
Found because TWAP and AC agreed to one decimal on all 26 ticker-side rows.
Fixed in v8; the AC family is now swept over 11 settings.

### 3.4 Benchmarks were too weak and not tuned
The agent is trained; the benchmarks were hand-set. Added:
- AC and POV swept across their full parameter ranges, compared at equal risk
  on the lower convex hull;
- **AC on a volume clock** — on expected volume, and on live volume with
  re-pacing by the day's realised volume (on a 0.3×-ADV day the first version
  left 24% of the order for the close; the re-paced version leaves <0.5%);
- **AC on live volume with a spread-aware rule**: each minute's quantity
  scaled by (typical spread / current quoted spread)^k, k = 0.5, 1, 2.

### 3.5 The agent could see hidden simulator state
The observation contained the true volatility-regime flag and the news-window
flag — information no real algorithm has.

- **Found:** the agent traded less than half as much in volatile regimes;
  zeroing the flags at evaluation removed ~¾ of its edge over the best
  classical strategy (interval then included zero).
- **Fix:** `honest_obs` replaces them with realised volatility of the mid
  over the last 15 minutes and the **current quoted spread** (public before
  trading).
- **Finding along the way:** realised volatility barely separates the regimes
  (0.22 vs 0.23) because regime noise is scaled ×0.1 in the price path while
  real data dominates. The volatile regime raises costs without moving the
  simulated price — a simulator inconsistency (§6).

### 3.6 Episodes were not paired; one still was not
Strategies originally drew independent episodes (7.7% landed on the same
ticker — chance). Fixed in v8. A residual bug: benchmarks in episode 0 drew a
random urgency before the day, putting them on a different day from the
agent. Fixed; every evaluation now prints a pairing check.

### 3.7 Smaller bugs found
- `spread_impact_exp` and `vol_impact_exp` were never passed from the config
  to the simulator (defaults happened to equal the config values).
- `spread_widening_factor` was never read; removed.
- The best checkpoint was selected on 20 **test-period** episodes. Now chosen
  on the last 10% of the training window (`val_frac`).
- Two of three "Agent B" models were byte-identical copies: training had
  failed and `copy best_model.zip` duplicated the previous model. Every
  training run now deletes `best_model.zip` first, and model hashes are
  checked before evaluation.
- `jitter_check` mixed episodes from different folds sharing an episode id.

---

## 4. What was wrong with the agent

### 4.1 Wrong objective
The reward was eight hand-tuned terms that never charged permanent impact
and were not the evaluated quantity. Replaced with the Almgren-Chriss
objective per step:

`r_t = −(Δexecution + Δpermanent + Δfees) − λ(u)·f_t²·σ²`

with f_t the fraction of the order still held, λ(u) = 5e-5·400^u (spanning
the empirical AC frontier), market drift excluded (zero mean; its variance
is what λ prices). γ = 0.999 because the objective is the undiscounted
episode total.

### 4.2 Resting orders were too generous
With passive orders enabled the agent beat AC by 2.5–2.8 bps, almost entirely
by resting orders: zero impact, no participation cap, and an assumed 40%
fill probability that the tape cannot measure. With passive orders switched
off at evaluation, every run lost to AC. Passive execution is excluded from
the result; a fair version needs benchmarks that can also rest orders.

### 4.3 The action was clipped at zero
SB3 samples from an unbounded Gaussian and clips to [0, 1]. Every sample
below 0 became "trade nothing" with no gradient back, so the policy used the
region as an on/off switch: idle in **28–40%** of open minutes, trade size
swinging 2.1–2.3× minute to minute. With impact ∝ size^1.65, pause-and-catch-up
costs ~1.6× the temporary impact of trading evenly.

- **Fix:** `action_squash: sigmoid` — action space [−10, 10] mapped through a
  sigmoid, so the operating range is far from any clip. Benchmarks are
  converted with the exact inverse (max difference 0.0007 bps).
- **Effect:** idle 28% → 0.1%; gap to AC +0.8 → **+0.14 bps** on the
  average-volume impact model (Stage 1).

### 4.4 A clock-time action made it worse
Hypothesis: the share-of-volume action biases the agent toward volume
following, which costs money when impact is measured against average volume.
A log-scale clock-time action raised the gap to +1.3 bps — the log scale
amplified jitter. Hypothesis rejected; recorded because it was tested.

### 4.5 Stage 1: known optimum
On a simulator where temporary impact is priced against average volume, the
classical optimum is the AC frontier. With the fixes above the agent gets
within **0.14–0.46 bps** of it across the urgency range, and beats every POV
rate.

### 4.6 Stage 2: impact priced against live volume
`impact_volume_ref: bar` — temporary impact measured against the current
minute's volume, the standard practitioner form. Busy minutes become cheap,
so adaptive strategies can matter. This is the setting of §1.

### 4.7 One policy in twelve fails at low urgency → guardrail
Without a guardrail, urgency 0 was 1.71 bps worse than the best classical
strategy. Almost all of it was fold 1, seed 42: 39% of the order done by
three-quarters of the day (straight-line pace 75%), then a forced, expensive
catch-up (execution cost 16.5 bps vs the usual 3–4).

- **Fix:** an evaluation-time schedule guardrail for the agent only. If the
  order is more than a set band behind a straight-line pace, trade at least
  enough to close the excess over 10 minutes. It only ever adds to the
  policy's choice. Desks put this kind of control around any model.
- **Effect:** urgency 0 from +1.71 to −0.04 bps (5% band) or +0.13 (10%
  band); urgency 0.5–1 essentially unchanged.
- **Caveat:** two bands were tried and the better reported. They give similar
  results; it is a mild post-hoc choice and is stated as such.

---

## 5. How the edge shrank

| Stage | Claimed edge | What it actually was |
|---|---|---|
| Published (v1) | ~27% vs TWAP, ~30% vs AC | Clipped metric; AC = TWAP |
| Signed IS | 4 bps vs TWAP | Per-fill permanent impact |
| Cumulative permanent | +0.9 bps worse than AC | Wrong objective; clipped action |
| Mean-variance reward + passive | −2.5 bps vs AC | Generous resting-order model |
| Aggressive only, squashed action | +0.14 bps vs AC | **Near-optimal on a known optimum** |
| Live-volume impact, hidden flags | −0.28 vs best classical (1 fold) | Hidden simulator state |
| Honest observations (1 fold) | −0.31 vs best schedule | Held, but one period |
| Honest, 4 folds | tie at u ≥ 0.5, worse at u ≤ 0.25 | One failing policy at low urgency |
| **+ 5% guardrail, 4 folds** | **tie vs best classical; −0.1 to −0.25 vs best schedule** | **Final** |

---

## 6. Limitations

**Still open**
- **Simulator calibrated on the full dataset**, including every fold's test
  window (volume profile, spread level, regime transitions, impact
  exponents). The policy never sees test days; the world it trains in was
  built with knowledge of them. Fix: per-fold recalibration.
- **The edge over pure schedules depends on spread variation that is not
  calibrated**: news windows (2% of minutes, spread ×5) and the volatility
  multiplier on the spread are assumptions. The average spread (2.13 bps) is
  measured. Real minute-level spread variability can be measured from the
  tick data already held.
- **The volatile regime barely moves the simulated price** (§3.5).
- **Impact magnitudes** (`eta_temporary`, permanent level, spread and
  volatility exponents) are not identifiable from the public tape; 31 of
  10.5M classified trades exceeded 1% participation. Permanent level no
  longer affects comparisons (§3.2); temporary level does.
- **Passive execution** is excluded (§4.2).
- **Agent B** (linear average-volume action) has only one valid seed; not
  reported.
- **Guardrail band** chosen post hoc between two values (§4.7).

**Structural**
Synthetic simulator, never run against replayed order flow. No venue routing,
queue position, latency, multi-day or portfolio execution, or market
resilience. Hawkes kernel single-exponential while real activity has long
memory. Results are relative comparisons within the simulator. Hyperparameters
were not swept. Generalisation to unseen tickers was not measured.

**Data exclusions** (stated criteria, unchanged): five tickers for
partial-venue spreads, DUK for liquidity, five half-days per ticker, 1.2% of
bars clipped, tick-rule trades excluded from impact analysis (51.2%
accuracy, CI [49.9, 52.5]).

---

## 7. Calibrated from real data

| Parameter | Value | Source |
|---|---|---|
| Temporary impact exponent | 0.65 | 11.75M Lee-Ready-classified trades |
| Permanent impact shape (per trade) | 0.18 | 312M trade-horizon observations (now used only to motivate concavity; the order-level model uses the square-root law) |
| Average spread | 2.13 bps | 2 years, two methods |
| Activity clustering decay | 0.0132 | ACF over 6,409 ticker-days |
| Regime volatilities / transitions | 0.000396 / 0.001092; 0.0241 / 0.0531 | 2-state GMM |
| Intraday volume profile, per-ticker ADV | measured | 2 years, per minute |

---

## 8. Reproducing the result

```
python evaluation\make_stage1_configs.py 0,1,2,3 --no-passive --squash --impact-bar --honest-obs
REM per fold k and seed s (delete best_model.zip first):
python run.py --config configs\stage2_np_sq_ho\fold{k}.yaml --timesteps 10000000 --train-seed {s}
copy models\best_model.zip models\s2ho_f{k}_s{s}.zip

python evaluation\batch1_eval.py --folds 0,1,2,3 --model-prefix s2ho --n-episodes 400 --n-urgency 0 --out evaluation\final <overrides>
python evaluation\urgency_frontier.py --folds 0,1,2,3 --model-prefix s2ho --n-episodes 400 --urgencies 0,0.25,0.5,0.75,1 --rl-guard 0.05,10 --out evaluation\final_guard05 <overrides>
```
`<overrides>`: `market.permanent_impact_mode=cumulative`,
`market.impact_volume_ref=bar`, `reward_weights.disable_alpha_signal=true`,
`execution.enable_passive=false`, `execution.action_squash=sigmoid`,
`execution.drop_noise_obs=true`, `execution.honest_obs=true` (each as
`--set key=value`).

---

## 9. Open items, in priority order

1. Per-fold simulator recalibration (closes the leakage in §6).
2. Measure real minute-level spread variability; re-run the final evaluation
   with the simulated spread variation matched to it.
3. Retrain with more low-urgency episodes so the guardrail is a backstop, not
   a necessity.
4. Benchmarks that can rest orders, then revisit passive execution.
5. Generalisation to tickers not seen in training.
