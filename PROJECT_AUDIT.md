# RL Execution System — Audit v10

Supersedes v9 and every earlier version. **The headline results in v1–v8,
including the first published post, are withdrawn** (§9). v9 reported that the
agent *matched* the strongest classical strategy.

v10 adds Stage 3 (§2):

- the simulator is recalibrated for every test period on its training days
  only, and charges each minute's **real** quoted spread;
- the agent is retrained and tested on unseen stocks, across guardrail
  settings, against classical strategies inside the same guardrail, and
  against a rule built from its own behaviour;
- **a model-selection leak was found and fixed** (§2.8): the "best"
  checkpoint had been chosen on the test period. Every model was retrained
  with selection on the validation window. The leak had inflated the edge by
  0.05–0.13 bps, and every number in §1 is from the clean models.

The v9 tie turns out to have rested on the old simulated spread, which made
the spread-aware benchmark look better than it is. With real spreads and clean
model selection, the agent **beats every classical strategy tested by about
0.16–0.17 bps at urgency 0.25–0.5**. At urgency 0.75 the edge is smaller and
not significant, and at the two extremes it ties.

---

## 1. The result

13 US large-cap tickers, 488 trading days (Aug 2024 – Jul 2026), 1-minute
bars, orders of 5% of each ticker's ADV. **4 walk-forward periods × 3
independently trained policies = 12 runs**, each tested on 400 paired
episodes per side from its own unseen test window. Every strategy in an
episode trades the same ticker, day and price path. Each policy's checkpoint
was chosen on the last 10% of its training window, never on test data.

Cost is **signed implementation shortfall** (bps). The agent has an urgency
input that trades cost against risk, so it is compared with each classical
strategy **at the same risk**: agent mean cost minus the benchmark family's
mean cost at equal standard deviation of cost, read off the lower convex hull
of that family's settings, per fold.

| Urgency | vs best classical (all 15 families) | runs better (of 12) | vs best schedule (no spread rule) | vs AC, time clock | vs AC, live volume | vs POV |
|---|---|---|---|---|---|---|
| 0 | −0.06 [−0.14, +0.01] | 6 | −0.06 [−0.14, +0.01] | −0.06 | −0.50 | −5.29 |
| 0.25 | **−0.17** [−0.26, −0.07] | 8 | **−0.17** [−0.26, −0.07] | −0.33 | −0.42 | −2.37 |
| 0.5 | **−0.16** [−0.31, −0.03] | 7 | **−0.18** [−0.33, −0.04] | −0.55 | −0.43 | −0.83 |
| 0.75 | −0.14 [−0.30, +0.04] | 7 | −0.18 [−0.34, +0.01] | −0.51 | −0.37 | −0.60 |
| 1 | −0.11 [−0.25, +0.08] | 7 | −0.13 [−0.29, +0.05] | −0.42 | −0.25 | −0.55 |

Negative = agent cheaper. Brackets: 95% interval from 1,000 bootstrap draws
resampling whole ticker-days, with every hull rebuilt on each draw.
Configuration: Stage 3 market (§2.1–2.2), honest observations, spread inputs
measured against the order's own running spread (§2.4), training urgency
U², **5% schedule guardrail fixed before these models were trained** (§2.9).
Models: `s3v`.

**"All 15 families"** means:

- the original benchmark families: AC on a time clock, on an expected-volume
  clock and on a live-volume clock; POV; and the live-volume clock with a
  spread rule (k = 0.5, 1, 2);
- the live-volume and spread-aware schedules run **inside the agent's
  guardrail** (§2.10);
- four versions of a **hand-written rule distilled from the agent's
  behaviour** (§2.11).

Each family is swept over its dial, and the cheapest at each risk is used.

**Per run.** The edge is uneven across test periods. Fold 3 is
consistently negative (down to −0.71). Fold 1 is slightly positive at low
urgency (up to +0.29) and negative at high urgency. Fold 0 is slightly positive
at high urgency (up to +0.24).

**In words.** Trained from scratch on public information only, in a simulator
calibrated without seeing the test periods and charging the real
minute-by-minute spread, with checkpoints selected without seeing them, the
agent beats every classical strategy tested at urgency 0.25–0.5 by about a
sixth of a basis point. It is not significantly different elsewhere. The
edge:

- does not come from the guardrail and does not depend on its setting
  (§2.9–2.10);
- carries over to unseen stocks at a small cost (§2.12);
- is only partly reproduced by a rule built from the agent's own behaviour
  (§2.11).

Without its guardrail the policy is not usable at low urgency.

**Magnitudes.** Mean cost is about 9.4–11 bps; the per-order standard
deviation is about 90–120 bps. An edge of 0.16 bps is roughly 1.5% of cost.
That is small, and it is why paired episodes, four test periods and clustered
intervals are needed.

---

## 2. Stage 3 — what was done after v9, and what each step found

v9 listed five open items:

1. calibration leakage;
2. uncalibrated spread variation;
3. dependence on the guardrail;
4. passive orders;
5. unseen tickers.

Stage 3 addressed 1, 2, 3 and 5. Each subsection gives the change, the
measurement and the effect.

### 2.1 Per-fold calibration, training days only
Every calibrated quantity is now re-measured for each fold on that fold's
training days only (`evaluation/calibrate_fold.py`):

- average spread;
- per-ticker ADV;
- volatility;
- regime parameters;
- Hawkes decay;
- intraday volume profile.

The script prints the full-sample and training-only values side by side.

| Quantity | Full sample vs training only | Verdict |
|---|---|---|
| Average spread | overstated by **+24% / +14% / +10%** in folds 1–3 (fold 0: −0.7%); spreads widened over the two years: 2.26 → 2.97 → 3.47 → 3.86 bps | the one material look-ahead |
| Per-ticker ADV | within ±10% except SPY in fold 0 (−18%); `load_csv_data` computed ADV over every day in the file, **test days included** — now overridden by a training-only map | small leak, closed |
| Intraday volume profile | total-variation distance 0.3–0.7% | negligible |
| Regime parameters | within ±4% (transition probabilities ±9%) | negligible |

**Consistency check:** each fold's training-only numbers equal the previous
fold's full-sample numbers exactly, as an expanding window should.

Two calibration errors were found along the way:

- **`volatility_per_min` was 0.0003 in every earlier config; the measured
  value is 0.00083–0.00094 (≈3× higher).** It scales the agent's volatility
  input, which was therefore saturated most of the time, and the volatility
  factor in impact.
- **Hawkes decay is 0.056, not 0.0132.** The measurement uses the same method
  as the original script (pooled autocorrelation of demeaned log
  volume-share residuals, exponential fit on lags 1–30). The autocorrelations
  are 0.22 / 0.13 / 0.08 / 0.044 / 0.016 at lags 1 / 5 / 15 / 30 / 60, which a
  53-minute half-life (0.0132) cannot produce. The old value was probably fitted
  against a volume profile from a different dataset. The kernel is not a single
  exponential (≈0.13/min early, ≈0.035/min at long lags); 0.056 is a middle
  value.

### 2.2 Real minute-level spreads
In the old simulator the spread charged each minute was
`avg × U-shape × volatility × depth × random news spikes`. Its variation was
assumed, not measured. `evaluation/measure_spread.py` compares spread
divided by its ticker-day median, real against simulated:

| Statistic | Old spread model | Real data (fold-3 file) |
|---|---|---|
| Minutes with spread > 2× the day's median | 4.1% | 8.4% |
| 99th percentile of spread / median | 5.0 | 7.0 |
| Autocorrelation at lag 1 / 5 / 15 min | 0.63 / 0.53 / 0.38 | 0.52 / 0.38 / 0.31 |
| Median ratio, first 30 min | 1.28 | 1.70 |
| Median ratio, midday | 0.72 | 1.00 |
| Median ratio, last 30 min | 1.32 | 1.00 |

The old model had half as many wide minutes as the data, made them too
persistent (so the previous minute's spread forecast the next one too well)
and invented a narrow-midday / wide-close shape. The real day is flat after
the first half hour.

**Fix** (`market.spread_source: data`): the spread charged each minute is
that minute's real quoted spread, widened only by the order's own depletion
of depth. The synthetic news spikes are gone. A strategy observes the
**previous** minute's spread, because the current bar's value averages over
the minute about to be traded. Volatility (`vol_source: data`) is the
realised volatility of the real midpoint over the last 15 minutes.

*Caveat:* the "real data" column above was measured through the simulator's
data-mode spread (lagged, with own-depth widening), not on the raw file.

### 2.3 Where the edge comes from: an ablation
The 12 v9 models were evaluated unchanged in the new market, then with one
change at a time switched back. Gap to best classical, with the guardrail:

| Market | u = 0 | u = 0.5 | u = 1 |
|---|---|---|---|
| Old market (v9 result) | −0.04 | −0.08 | +0.07 |
| Stage 3 market (real spreads + real volatility) | −0.14* | −0.29* | −0.24* |
| A: real spreads, old volatility model | −0.14* | −0.21* | −0.14* |
| B: old spread model, real volatility | −0.23* | −0.01 | +0.07 |

\* = 95% interval excludes zero.

**Real spreads drive the change; the volatility switch does not.** With the old
spread model (B) the spread-aware benchmark is strong and ties the agent. With
real spreads it falls behind plain AC (spread-aware k = 2 was ~1 bp behind
the agent), while the agent keeps its edge. The persistent synthetic spread
had made "trade less when the spread is wide" look better than it is.

No look-ahead: the agent and the spread-aware benchmark both observe the
previous minute's spread and pay the current minute's.

### 2.4 The old models leaned on the guardrail; the spread input drifted
Without the guardrail the same v9 models cost **1 bp more** at urgency 0.5.
Every seed was affected, in proportion to its fold's spread drift:

| Fold | Guardrail saves (bps) | Training-window spread vs whole fold |
|---|---|---|
| 1 | 2.4 | −24% |
| 2 | 1.0 | −14% |
| 0 | 0.4 | +0.7% |
| 3 | 0.3 | −10% |

The agent's spread input was the quote divided by one fixed calibrated level.
In a test period where spreads were 10–25% wider, almost every minute looked
"wide", and the agent had learned to wait when the spread was wide. It fell
behind and then paid to catch up.

**Fix** (`execution.spread_obs_ref: running`): the spread input becomes the
quote relative to the mean of the quotes seen so far in this order (the same
causal reference the spread-aware benchmark uses). The slow level moves to a
separate input.

### 2.5 Retraining (12 models) with more patient episodes
> **Note.** The models in §2.5–2.7 had their best checkpoint chosen on the
> **test** period, because of a bug found later (§2.8). Their numbers are kept
> as development history. Every result in §1 and §2.9–2.12 comes from models
> retrained with selection on the validation window.

All 12 policies were retrained in the Stage 3 market with training urgency
drawn as U² (half the episodes below u = 0.25, up from a quarter), so that
patient orders are no longer rare.

| Urgency | No guardrail | 5% guardrail | v9 (old market, 5% guardrail) |
|---|---|---|---|
| 0 | +3.98* | −0.05 | −0.04 |
| 0.25 | +1.40* | **−0.31*** | −0.11* |
| 0.5 | +0.34 | **−0.38*** | −0.08* |
| 0.75 | +0.03 | **−0.30*** | −0.01 |
| 1 | −0.02 | −0.17 | +0.07 |

(Gap to best classical over the original 7 families; §1 adds 8 more.)

**With the guardrail this is the best result of the project. Without it, the
low-urgency failure is worse than in v9.** More patient training episodes did
not make the guardrail a backstop.

Guarded per-run gaps, fold × seed:

- all are within +0.30 bps of the best classical strategy at every urgency;
- fold 1, the problem fold without the guardrail, is −0.2 to −0.8 at
  u = 0.5–1;
- jitter is normal: trade-size swing is 1.84× minute to minute (POV 20%:
  1.61×), and the agent is idle in 0.9% of minutes.

### 2.6 Why the unguarded agent fails at low urgency
`evaluation/diagnose_low_urgency.py` compares the unguarded agent with TWAP
on the same episodes, at urgency 0:

| | Fold 0 | Fold 1 | Fold 2 | Fold 3 |
|---|---|---|---|---|
| Gap vs TWAP (bps) | +1.96 | **+10.02** | +2.41 | +2.37 |
| Share of order done at 25% / 50% / 75% of the day (TWAP: 25 / 50 / 75) | 35 / 56 / 74 | **30 / 45 / 60** | 35 / 55 / 74 | 32 / 52 / 72 |
| Test-day volume / training ADV | 0.95 | **0.64** | 0.82 | 0.78 |

- **The extra cost is all execution cost.** Drift and permanent impact
  differences are ≈0, so this is not bad luck with prices.
- **The cost sits on wide-spread days.** By tercile of the day's spread
  relative to the training average, the narrowest and middle thirds cost
  about −0.2 to +0.8 bps. The widest third costs **+6 bps in folds 0, 2 and 3
  and +29.6 in fold 1**.
- **Low-volume days add to it**, because catching up late in a thin day is
  expensive.
- **Worst tickers:** JPM (+22), CVX, MSFT, TSLA, PG — mostly the
  lower-volume names.
- **Mechanism:** the slow spread-level input still says "today is wide,
  wait". With aggressive-only orders the spread is paid on every share
  whatever the timing, so the level carries no timing information. The policy
  learned a spurious cue.

### 2.7 A fix that failed (Stage 3b) — reported as a negative result
Two changes were tried together:

- **drop the spread-level input** (`drop_spread_level`);
- **train with the guardrail switched on** (`train_guard_band`), so the
  policy learns under the constraint it is deployed with.

| Urgency | 3b, guardrail | 3b, no guardrail | Stage 3, guardrail |
|---|---|---|---|
| 0 | +0.17* | +8.82* | −0.05 |
| 0.25 | +0.12 | +3.03* | −0.31* |
| 0.5 | +0.06 | +0.37* | −0.38* |
| 0.75 | +0.11 | +0.12 | −0.30* |
| 1 | +0.13* | +0.14* | −0.17 |

- **Worse on both counts.** Trained with a safety net, the policy learned to
  wait and let the guardrail catch it up.
- **Without the guardrail, fold 1 collapses:** 16% / 22% / 26% done at the
  quarter / half / three-quarter marks, +24 bps.
- **With the guardrail, the edge is gone.**
- **The trigger survives:** dropping the level input did not remove the
  wide-spread pattern.

The two changes were made at once, so their separate effects are not
identified. **Stage 3 (guardrail at evaluation only) is the reported
system.**

### 2.8 A model-selection leak, found while reworking the training code
`agent/train.py` has a `val_frac` setting for choosing the best checkpoint
on the end of the training window, and v8 recorded that leak as closed.
**It was not.** The validation set was split off but never used:

```python
train_df, val_df = train_test_split_days(train_df, test_frac=val_frac)   # computed...
eval_env = make_vec_env(make_env_fn(cfg, test_df, ...))                   # ...test_df used
```

So `best_model.zip` was the best of about 2,000 checkpoints, each scored on
20 test-period episodes (an evaluation every 5,000 steps over 10M). This
affected every model since v8, including all of §2.5–2.7.

**Fix.** Selection now uses the validation tail. The trainer refuses to run
without one, and every training log prints which set was used. Evaluation
runs every 25,000 steps instead of every 5,000, so the best of 400
candidates is chosen instead of 2,000; §2.13 has why. All 12 models were
retrained (`s3v`), and the headline was re-run on the same episodes and
benchmarks:

| Urgency | Checkpoint chosen on test (`s3`) | Chosen on validation (`s3v`) |
|---|---|---|
| 0 | −0.05 | −0.06 |
| 0.25 | −0.22* | **−0.17*** |
| 0.5 | −0.29* | **−0.16*** |
| 0.75 | −0.23* | −0.14 |
| 1 | −0.12 | −0.11 |

(Gap to best classical, all 15 families; * = 95% interval excludes zero.)

**The leak inflated the edge by 0.05–0.13 bps** (up to 45% at u = 0.5), and
the result at u = 0.75 loses significance. Two things changed at once, the
selection set and the evaluation frequency, so this measures their combined
effect. Choosing among fewer candidates should, if anything, reduce the
lucky-pick effect, so both changes point the same way.

### 2.9 Guardrail sensitivity (clean models)
The same 12 `s3v` models and the same episodes, with only the guardrail
changed. The gap is against the best of the original 7 families
(`evaluation/guard_sensitivity.py`):

| Urgency | None | 2.5%, 10 min | **5%, 10 min** | 10%, 10 min | 5%, 5 min | 5%, 30 min |
|---|---|---|---|---|---|---|
| 0 | +6.19* | −0.19* | −0.06 | +0.27* | −0.13* | +0.30* |
| 0.25 | +2.92* | −0.32* | −0.24* | −0.05 | −0.28* | −0.04 |
| 0.5 | +1.32* | −0.30* | −0.26* | −0.16* | −0.28* | −0.15* |
| 0.75 | +0.53* | −0.24* | −0.21* | −0.16 | −0.22* | −0.15 |
| 1 | +0.17 | −0.17 | −0.16 | −0.15 | −0.16 | −0.14 |
| Worst single run | +21.35 | +0.23 | +0.29 | +0.83 | +0.23 | +0.91 |

- **The guardrail is essential.** The clean policy alone is worse than the
  leaky one: +6.2 bps at u = 0 and significantly worse than classical even
  at u = 0.5 and 0.75. Choosing checkpoints on the test period had partly
  hidden this.
- **Any tight guardrail works:** 2.5%, or 5% with fast catch-up, gives
  −0.24 to −0.32 at u = 0.25–0.75.
- **Loose settings lose the u = 0.25 edge.** With a 10% band or a 30-minute
  catch-up it falls to about −0.05, and they cost at u = 0.
- **The headline stays at the pre-fixed 5%.** Picking the best-looking 2.5%
  now would be selection on the test set. The honest statement is that the
  edge depends on keeping the agent close to schedule; the exact band
  matters little within 2.5–5%.

### 2.10 Classical strategies inside the same guardrail
The agent is always evaluated with the guardrail; the benchmarks were not.
The live-volume and spread-aware AC families were therefore re-run inside the
identical 5% / 10-minute guardrail (`gacl`, `gacs`). They are almost never 5%
behind, so the guardrail barely changes them: on the `s3` models it moved the
agent's gap by only ≈0.03 bps. The edge does not come from the guardrail.

### 2.11 What the agent learned, and whether a rule can copy it
`evaluation/behaviour_probe.py` records every minute for the agent and for
benchmarks on the same episodes (`s3v`, 4 folds × 3 seeds × u = 0.25 / 0.5 /
0.75, 40 episodes per side per fold; 601k agent-minutes).

**Where the cost goes** (u = 0.5, bps of the order):

| Strategy | Execution | Half-spread paid | Impact | Spread paid / day's average | Participation |
|---|---|---|---|---|---|
| RL agent | 4.20 | 2.53 | 1.67 | 1.21 | 14.1% |
| AC@0.05 | 4.17 | 2.75 | 1.42 | 1.15 | 7.2% |
| AC live @0.05 | 4.59 | 3.13 | 1.47 | 1.32 | 7.3% |
| AC live + spread k=1 @0.05 | 4.91 | 3.01 | 1.90 | 1.32 | 7.5% |
| TWAP | 3.49 | 2.36 | 1.13 | 1.00 | 7.2% |

The agent does **not** win by catching narrow spreads: it pays 21% above the
day's average spread, because, like AC, it trades heavily in the wide opening
minutes. Its saving is **impact**: 1.67 bps while taking twice the share of
volume.

**What it reacts to** (pace relative to an even pace over the time left,
lowest → highest decile of each input):

| Input | Agent | AC live + spread k=1 |
|---|---|---|
| Last minute's volume | 1.0× → 4.1× | 0.6× → 5.0× |
| Recent volatility | **2.8× → 1.0×** | 0.7× → 3.5× |
| Spread vs earlier in the order | ~2.5× flat, then **0.8× above ≈1.4×** | 4.0× → 0.6×, steadily |
| Adverse price move since arrival | ≈ flat | ≈ flat |

- **Follows volume.** It trades more in busy minutes, as the live-volume
  clock does.
- **Slows down in volatile minutes; the spread-aware benchmark speeds up.**
  Impact grows with volatility in the simulator, so calm minutes are cheaper.
- **Pauses only for very wide spreads.** It otherwise ignores the spread.

A linear model and a depth-3 tree explain R² ≈ 0.44 of its log pace. The
coefficients per standard deviation are: spread −0.27, volume +0.13,
volatility −0.12, time −0.21, schedule position +0.67. **This is the same
pattern as the leaky models** (R² 0.42), so the mechanism does not depend on
the selection bug.

**The rule.** The rule tested is the guarded live-volume AC, with each
minute's quantity scaled by (typical / current realised volatility)^kv, for
kv = 0.5 and 1, with and without the spread rule k = 1. It uses the same
15-minute volatility the agent sees.

| Urgency | Best of the 7 original families | Best of all 15 (adds guarded strategies and rules) |
|---|---|---|
| 0.25 | −0.24* | −0.17* |
| 0.5 | −0.26* | −0.16* |
| 0.75 | −0.21* | −0.14 |

- **The extra strategies close 0.07–0.10 bps, about a third of the gap.**
  Almost all of that is the volatility rule, since the guardrail alone moved
  the gap by only ≈0.03 (§2.10).
- **The comparison favours the rule.** It was designed after watching the
  agent on test episodes, its strength is chosen per frontier like AC's, and
  it sees the current minute's volume while the agent sees the previous
  minute's.

### 2.12 Unseen stocks (clean models)
Fold 3; the 13 tickers are split into 4 groups:

- group 0: AAPL, JPM, QQQ, XOM;
- group 1: BAC, MSFT, SPY;
- group 2: CVX, NVDA, TSLA;
- group 3: GOOGL, PG, WMT.

For each group, three models were trained **without** those tickers
(`s3vu`) and tested only on them. They were compared on identical episodes
with the normal fold-3 `s3v` models (three seeds), which were trained on all
tickers. Gap to best classical (original 7 families), at each model's own
risk:

| Urgency | Never saw the stocks | Saw them | Difference |
|---|---|---|---|
| 0 | −0.02 | −0.13 | +0.11 |
| 0.25 | −0.33 | −0.41 | +0.08 |
| 0.5 | −0.43 | −0.51 | +0.07 |
| 0.75 | −0.33 | −0.23 | −0.10 |
| 1 | −0.15 | −0.06 | −0.09 |

**A small cost from never having seen a stock at low and medium urgency
(≈0.07–0.11 bps), none at high urgency.** The edge over classical survives
on unseen stocks. Per group at u = 0.5, unseen: +0.07 / −0.32 / −1.06 / −0.42
(groups 0–3).

Caveats:

- fold 3 only;
- **groups 2 and 3 have two unseen models instead of three** (one training
  each did not produce a model);
- the held-out models trained on 9–10 tickers rather than 13;
- the comparison set excludes the guarded and rule families.

### 2.13 Training infrastructure: measured, then made 2× faster
`evaluation/bench_train.py` trains for a fixed number of steps under
different settings and splits the wall time into simulation, network
updates and checkpoint evaluation. The machine is an i5-12400F (6 cores,
12 threads) with an RTX 4060 Ti.

| Setting | Steps/s (total) | Time split: simulate / update / evaluate | 12 × 10M models |
|---|---|---|---|
| CPU, 1 run, evaluation every 5k steps (old) | 1,874 | 56% / 16% / 28% | 17.8 h |
| CPU, 1 run, no evaluation | 2,617 | 78% / 22% / – | 12.7 h |
| GPU (network on CUDA), 1 run, no evaluation | 1,664 | – | 20.0 h |
| CPU, 3 runs at once, 1 thread each, with evaluation | 3,998 | 53% / 25% / 22% | 8.3 h |
| CPU, 4 runs at once, no evaluation | 4,283 | – | 7.8 h |

- **The GPU is 43% slower.** The work is the market simulator, which runs
  on the CPU. The policy network (two layers of 256) is too small to pay for
  copying data to the GPU every step.
- **Running 3 trainings at once is 2.1× faster.** It fills the time one run
  spends updating or evaluating; 4 at once adds almost nothing.
- **The single-process checkpoint evaluation took 28% of training time.**
  Running it 5× less often removes most of that without changing what is
  trained.
- **Same training, different scheduling.** The number of simulator workers
  per run stays 8, because it sets PPO's rollout size.

`evaluation/parallel_train.py` runs N trainings at once, each in its own
folder. A run that produces no model is reported as failed rather than
silently replaced by an old file, and all model hashes are printed at the end.

**Real result:** the 12 clean models took **10.1 h instead of about 20 h**
(about 3,300 steps/s; a real run has start-up and logging overheads the
benchmark does not).

### 2.14 Honest accounting of test-set use
The four test periods have been looked at many times during development (v8
→ v10), and each round of "look, change, retest" spends some of their
credibility. §2.8 shows how much a hidden selection on the test period was
worth (0.05–0.13 bps), which gives a sense of scale. Mitigations:

- checkpoint selection now never sees test data;
- the guardrail band was fixed before the Stage 3 models were trained, and
  §2.9 shows the result does not hinge on it within 2.5–5%;
- the training procedure was not changed after the final results were seen
  (the one attempt, 3b, is reported as failed);
- the unseen-stock test uses tickers the models never trained on;
- the distilled rule was tuned with knowledge of the agent, which biases the
  comparison toward the rule.

A clean confirmation needs a period that has not been looked at (data after
Jul 2026) or paper trading.

---

## 3. How the edge moved

| Stage | Reported edge | What it actually was |
|---|---|---|
| Published (v1) | ~27% vs TWAP, ~30% vs AC | Clipped metric; AC = TWAP |
| Signed IS | 4 bps vs TWAP | Per-fill permanent impact |
| Cumulative permanent | +0.9 bps worse than AC | Wrong objective; clipped action |
| Mean-variance reward + passive | −2.5 bps vs AC | Generous resting-order model |
| Aggressive only, squashed action | +0.14 bps from AC optimum | Near-optimal on a known optimum |
| Live-volume impact, hidden flags | −0.28 vs best classical (1 fold) | Hidden simulator state |
| Honest observations, 4 folds + guardrail (v9) | tie with best classical | Spread-aware benchmark flattered by persistent synthetic spreads |
| v9 models in Stage 3 market | −0.14 to −0.29 | Leaned on the guardrail (spread-level drift) |
| Stage 3 retrained + guarded benchmarks + rule | −0.22 to −0.29 at u 0.25–0.75 | Checkpoint chosen on the test period |
| Stage 3b (trained with guardrail) | +0.06 to +0.17 | Negative result; not used |
| **Clean checkpoint selection (final)** | **−0.17 / −0.16 at u 0.25 / 0.5; n.s. elsewhere** | **Final** |

---

## 4. Limitations

**Open**

- **The agent alone is not usable at low urgency.** Without the guardrail
  it costs +6.2 bps more than classical at u = 0 and is significantly worse
  up to u = 0.75 (§2.9). It fails on low-volume, wide-spread days after
  spreads drift (§2.6). The guardrail is part of the method: fixed in advance,
  and any tight setting (2.5–5%) gives the result.
- **The edge is small and uneven.** It is significant only at u = 0.25–0.5,
  about 1.5% of cost, and it varies by test period (fold 3 strong, folds 0
  and 1 mixed).
- **The volatility response rides on an assumed link.** Temporary impact
  scales with volatility^0.4 in the simulator, and the agent's most
  distinctive behaviour is to slow down when volatility is high. The exponent
  is not identifiable from the public tape. Ablation A (§2.3), with volatility
  from the hidden regime model instead, kept most of the edge, so it does not
  rest on this alone.
- **Impact magnitudes are assumed.** `eta_temporary` and the
  spread/volatility exponents cannot be measured from public data (31 of
  10.5M classified trades exceeded 1% participation). The permanent level no
  longer affects comparisons.
- **Passive execution is excluded** (§11.2). Fixing it needs a queue and fill
  model and benchmarks that can rest orders.
- **The Hawkes kernel is single-exponential**, while real volume clustering
  has long memory (§2.1).
- **The test periods have been reused** (§2.14).
- **Unseen-stock test:** fold 3 only, with a reduced comparison set, and two
  groups have two models instead of three.

**Closed in v10**

- calibration leakage (§2.1);
- uncalibrated spread variation (§2.2);
- the volatile regime barely moving the simulated price — volatility now
  comes from the real midpoint in data mode;
- the guardrail band chosen post hoc (§2.9);
- checkpoint selection on test data (§2.8);
- generalisation to unseen tickers (§2.12).

**Structural**

- The simulator is synthetic and has never been run against replayed order
  flow.
- Not modelled: venue routing, queue position, latency, multi-day or
  portfolio execution, and market resilience.
- Results are relative comparisons within the simulator.
- Hyperparameters were not swept.

**Data exclusions** (stated criteria, unchanged):

- five tickers for partial-venue spreads;
- DUK for liquidity;
- five half-days per ticker;
- 1.2% of bars clipped;
- tick-rule trades excluded from impact analysis (51.2% accuracy,
  CI [49.9, 52.5]).

---

## 5. Calibrated from real data

| Parameter | Value | Source |
|---|---|---|
| Spread charged each minute | the real quoted spread that minute (Stage 3) | 1-minute bars |
| Average spread (per fold, training days) | 2.27 / 2.26 / 2.97 / 3.47 bps | `calibrate_fold.py` |
| Per-ticker ADV | training days only, per fold | `calibrate_fold.py` |
| 1-minute volatility | 0.00085–0.00093 (was 0.0003) | training days, per fold |
| Activity clustering decay | 0.056 (was 0.0132) | ACF of volume residuals, per fold |
| Regime volatilities / transitions | ≈0.00038 / 0.0013; ≈0.020 / 0.053 | 2-state GMM, per fold |
| Intraday volume profile | per fold, training days | per minute |
| Temporary impact exponent | 0.65 | 11.75M Lee-Ready-classified trades |
| Permanent impact | square-root law on cumulative order (shape 0.18 per trade motivates concavity) | 312M trade-horizon observations |

---

## 6. Reproducing the result

```
REM configs per fold (training days only), unseen-ticker configs too
python evaluation\calibrate_fold.py --folds 0,1,2,3 --base configs\stage2_np_sq_ho --urgency-power 2 --unseen-groups 4 --unseen-fold 3

REM 12 trainings, 3 at a time, checkpoint selection on the validation window (~10 h)
python evaluation\parallel_train.py --configs "configs\stage3\fold{fold}.yaml" --folds 0,1,2,3 --seeds 42,43,44 --prefix s3v --max-parallel 3 --torch-threads 1 --eval-freq 25000

REM benchmarks (incl. guarded families and distilled rules), then the agent with the 5% guardrail
python evaluation\batch1_eval.py --folds 0,1,2,3 --model-prefix s3v --config-pattern "configs\stage3\fold{fold}.yaml" --n-urgency 0 --n-episodes 400 --out evaluation\stage3v_gbench
python evaluation\batch1_eval.py --folds 0,1,2,3 --model-prefix s3v --config-pattern "configs\stage3\fold{fold}.yaml" --n-urgency 0 --n-episodes 400 --out evaluation\stage3v_gbench --append --no-rl --bench-prefixes gacl,gacs,gacv --bench-guard 0.05,10
python evaluation\urgency_frontier.py --folds 0,1,2,3 --model-prefix s3v --config-pattern "configs\stage3\fold{fold}.yaml" --n-episodes 400 --urgencies 0,0.25,0.5,0.75,1 --rl-guard 0.05,10 --out evaluation\stage3v_gbench
```

`--bench-prefixes gacl,gacs,gacv` also picks up the `gacs1v` rules.

Diagnostics:

- `measure_spread.py`
- `diagnose_low_urgency.py`
- `guard_sensitivity.py`
- `behaviour_probe.py`
- `compare_unseen.py`
- `bench_train.py`

The command lists `stage3_commands.txt`, `stage3c_commands.txt` and
`stage3v_rerun_commands.txt` have the full runs.

---

## 7. Open items, in priority order

1. A clean out-of-sample confirmation on data after Jul 2026 (§2.14).
2. Make the policy itself robust to spread and volume regime shifts at low
   urgency, so the guardrail is a backstop — for example by training on
   randomised spread levels and volume regimes. Training with the guardrail
   switched on does not work (§2.7).
3. Benchmarks that can rest orders, then passive execution with a queue
   model.
4. A batched (GPU) version of the simulator; the profile in §2.13 shows the
   simulator is the bottleneck.
5. A long-memory volume-clustering kernel; replay against historical order
   flow; then paper trading.

---

## 8. Earlier history

Sections 9–11 are carried over from v9 unchanged, apart from numbering,
cross-references and one correction (§10.7, model selection). They record the
problems found in v1–v9.

---

## 9. Withdrawn claims (v1–v8)

| Published / earlier claim | Status | Reason |
|---|---|---|
| ~27% cheaper than TWAP/VWAP | **Withdrawn** | Clipped cost metric (§10.1) and per-fill permanent impact (§10.2) |
| ~30% cheaper than Almgren-Chriss (v1–v7) | **Withdrawn** | AC was implemented as TWAP (v8), then the two issues above |
| +11–12% vs Almgren-Chriss (v8) | **Withdrawn** | Same two issues |
| Loses to POV 20% | Reversed | The clipped metric penalised slower strategies; under signed IS the agent beats every POV rate |
| Training-seed std 0.8–1.4 pts (v8) | Superseded | Seed effects now reported per urgency level; one policy in twelve fails at low urgency without the guardrail |

The clipped metric reproduced the published table exactly when re-run on the
same models (+27.2% buy vs TWAP), which is how its effect was confirmed.

---

## 10. Measurement and market-model fixes (v8–v9)

Each item: what was wrong, how it was found, the fix, and the measured
effect.

### 10.1 The cost metric charged bad luck and ignored good luck
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

### 10.2 Permanent impact was charged per fill, not per order
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

### 10.3 Almgren-Chriss was TWAP (v8)
`risk_aversion` 1e-6…1e-2 made κ so small the AC schedule was linear.
Found because TWAP and AC agreed to one decimal on all 26 ticker-side rows.
Fixed in v8; the AC family is now swept over 11 settings.

### 10.4 Benchmarks were too weak and not tuned
The agent is trained; the benchmarks were hand-set. Added:
- AC and POV swept across their full parameter ranges, compared at equal risk
  on the lower convex hull;
- **AC on a volume clock** — on expected volume, and on live volume with
  re-pacing by the day's realised volume (on a 0.3×-ADV day the first version
  left 24% of the order for the close; the re-paced version leaves <0.5%);
- **AC on live volume with a spread-aware rule**: each minute's quantity
  scaled by (typical spread / current quoted spread)^k, k = 0.5, 1, 2.

### 10.5 The agent could see hidden simulator state
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
  simulated price — a simulator inconsistency (§6 of v9; closed in v10, §2.2).

### 10.6 Episodes were not paired; one still was not
Strategies originally drew independent episodes (7.7% landed on the same
ticker — chance). Fixed in v8. A residual bug: benchmarks in episode 0 drew a
random urgency before the day, putting them on a different day from the
agent. Fixed; every evaluation now prints a pairing check.

### 10.7 Smaller bugs found
- `spread_impact_exp` and `vol_impact_exp` were never passed from the config
  to the simulator (defaults happened to equal the config values).
- `spread_widening_factor` was never read; removed.
- The best checkpoint was selected on 20 **test-period** episodes. Now chosen
  on the last 10% of the training window (`val_frac`). **Correction (v10):**
  this fix was incomplete. The validation set was split off but the
  evaluation still used the test period, until §2.8.
- Two of three "Agent B" models were byte-identical copies: training had
  failed and `copy best_model.zip` duplicated the previous model. Every
  training run now deletes `best_model.zip` first, and model hashes are
  checked before evaluation.
- `jitter_check` mixed episodes from different folds sharing an episode id.

---

## 11. Agent fixes (v8–v9)

### 11.1 Wrong objective
The reward was eight hand-tuned terms that never charged permanent impact
and were not the evaluated quantity. Replaced with the Almgren-Chriss
objective per step:

`r_t = −(Δexecution + Δpermanent + Δfees) − λ(u)·f_t²·σ²`

with f_t the fraction of the order still held, λ(u) = 5e-5·400^u (spanning
the empirical AC frontier), market drift excluded (zero mean; its variance
is what λ prices). γ = 0.999 because the objective is the undiscounted
episode total.

### 11.2 Resting orders were too generous
With passive orders enabled the agent beat AC by 2.5–2.8 bps, almost entirely
by resting orders: zero impact, no participation cap, and an assumed 40%
fill probability that the tape cannot measure. With passive orders switched
off at evaluation, every run lost to AC. Passive execution is excluded from
the result; a fair version needs benchmarks that can also rest orders.

### 11.3 The action was clipped at zero
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

### 11.4 A clock-time action made it worse
Hypothesis: the share-of-volume action biases the agent toward volume
following, which costs money when impact is measured against average volume.
A log-scale clock-time action raised the gap to +1.3 bps — the log scale
amplified jitter. Hypothesis rejected; recorded because it was tested.

### 11.5 Stage 1: known optimum
On a simulator where temporary impact is priced against average volume, the
classical optimum is the AC frontier. With the fixes above the agent gets
within **0.14–0.46 bps** of it across the urgency range, and beats every POV
rate.

### 11.6 Stage 2: impact priced against live volume
`impact_volume_ref: bar` — temporary impact measured against the current
minute's volume, the standard practitioner form. Busy minutes become cheap,
so adaptive strategies can matter. Stage 3 (§2) keeps this impact model.

### 11.7 One policy in twelve fails at low urgency → guardrail
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
- **Caveat (v9):** two bands were tried and the better reported. **Superseded
  in v10:** the 5% band was then fixed and used unchanged for every Stage 3
  model, and a sensitivity check across bands and catch-up speeds (§2.9) shows
  the result does not depend on it.

---

