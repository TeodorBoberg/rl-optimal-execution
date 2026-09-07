# RL Execution System — Audit v6

Supersedes PROJECT_AUDIT_v5.md. Adds the permanent-impact correction, the
10-second decision-frequency experiment, and updated seed-study figures.

---

## 1. Headline result

**13 US large-cap tickers, 488 trading days each (Aug 2024 – Jul 2026),
1-minute bars, orders at 5% of each ticker's ADV, POV-style action space
with passive/aggressive split, fees and rebates modelled, concave
permanent impact.**

Mean across **three independently trained policies**, each evaluated at
1,000 episodes:

| | vs TWAP | vs VWAP | vs Almgren-Chriss |
|---|---|---|---|
| **BUY** | +28.5% ± 5.2% | +30.1% ± 5.1% | +30.6% ± 5.0% |
| **SELL** | +28.4% ± 1.9% | +26.2% ± 1.6% | +29.0% ± 4.7% |

| | vs POV 5% | vs POV 10% | vs POV 20% |
|---|---|---|---|
| **BUY** | +39.6% ± 4.4% | +23.3% ± 5.6% | **−5.8% ± 7.7%** ⚠ |
| **SELL** | +38.2% ± 3.0% | +15.4% ± 4.9% | **+0.3% ± 4.8%** ⚠ |

Error bars are training-seed standard deviations. **Always quote these,
never a single run** — see §4.1.

**POV 20% is not beaten.** This has now held under linear and concave
permanent impact, passive and pure-aggressive execution, 1-minute and
10-second decisions, four impact magnitudes, every walk-forward fold, and
every training seed tested.

---

## 2. What changed since v5

### 2.1 Permanent impact: functional form corrected
The simulator assumed `perm = gamma * participation` (linear, Kyle 1985).
Measured over **312M classified trade observations**, real permanent
impact is strongly concave: exponent **0.157 / 0.191 / 0.188** at 5 / 15 /
60 minute horizons, 11/11 buckets significant at every horizon, impact
flat across horizons (confirming genuinely permanent, not decaying
temporary impact).

Now `perm = gamma * participation ** 0.18`, with `gamma_permanent`
re-anchored from 5.0e-5 to 7.57e-6 so that impact at 10% participation
matches the previous linear model there. **The measured LEVEL was
deliberately not imported**: those observations sit at ~0.002%
participation while the simulator operates at 5-25%, and extrapolating a
power law across two to three orders of magnitude is the same error that
produced an implausible 868x value when attempted for `eta_temporary`.

**Effect: +3 to +5 points against schedule-based benchmarks, all within
one standard deviation.** Fixing the largest known modelling error moved
the headline by less than training-seed noise.

An initial prediction that this would *hurt* the agent was wrong. The
reasoning compared the agent's ~4-6% participation against POV20's nominal
20%, but POV20 actually executes at ~0.05-0.06 participation — the same
range. What concavity actually penalises is **fragmentation**: it charges
43x more at 0.1% participation and 6.6x more at 1%, so strategies
spreading many tiny fills across thin bars (TWAP, VWAP, AC at ~0.11-0.21
participation overall) are hit hardest.

### 2.2 Decision frequency: 10-second bars tested, no benefit
Rebuilt the dataset at 10-second granularity (2,340 steps/day, 14.8M
bars), retrained with `gamma` raised to 0.9997 for the longer horizon.
**17 hours of training versus 1.6.**

Only POV20 produced valid statistics at both frequencies (see §2.3):

| | 1-minute | 10-second |
|---|---|---|
| BUY vs POV20 | −2.5% | −26.8% |
| SELL vs POV20 | −9.0% | +6.9% |

No consistent improvement — worse on buys, better on sells, at 10x the
training cost. Combined with the credit-assignment problem at longer
horizons (a 60,000-step tick-level episode would need `gamma` ≈ 0.99998),
this is direct evidence that **finer decision frequency is not where the
value is**, which extends to the tick-level question.

### 2.3 Schedule-based benchmarks break at fine granularity
An unexpected finding from the 10-second run, and arguably more useful
than the headline it was testing.

At 2,340 steps a fixed-schedule strategy targets 1/2340th of the order per
bar, but 10-second bars are frequently empty (median 9.6% zero-volume,
max 72.2% on thin ticker-days). Schedule-based algos cannot trade through
an empty bar, accumulate backlog, and hit `force_fill` at the close:

| Strategy | Max participation | Max episode cost |
|---|---|---|
| POV5 sell | **26.18** | **28,043 bps** |
| TWAP buy | **8.30** | 6,538 bps |
| AC sell | 5.31 | 1,185 bps |
| POV10 buy | 4.25 | 1,778 bps |
| **RL agent** | **0.11 / 0.15** | 292 / 379 bps |

The RL agent degrades gracefully because its POV action scales with actual
bar volume — it trades nothing when there is nothing to trade and catches
up when liquidity returns. **This is a real argument for volume-based over
schedule-based execution**, independent of any RL result.

The 10-second comparisons against TWAP, VWAP, AC, POV5 and POV10 measure
benchmark breakdown, not execution quality, and **must not be quoted**.

---

## 3. Validation

**Walk-forward.** Fold 3 trains on days 0–380, tests on days 380–440 —
never seen — and reproduced the full-sample result.

**Statistical significance.** All six schedule-benchmark comparisons
p=0.0000, Bonferroni-corrected, n=3000 (measured pre-passive).

**Alpha ablation.** Removing the synthetic forecasting signal from both
reward and observation changes results by under 2.5pp. The improvement is
execution scheduling, not forecasting.

**Impact-magnitude sensitivity.** `eta_temporary` uncalibrated; tested at
1x/2x/5x/10x with a retrain at 5x. The edge narrows to 10–17% at 5x.

**Passive-assumption sensitivity.** `passive_fill_prob` swept 0.1 → 0.5
and the maker rebate set to zero: results moved under 1.5pp. In hindsight
this indicated the passive mechanism has little influence (§4.2), not that
it is robust.

---

## 4. Methodological findings

### 4.1 Single training runs are unreliable in this system
Training-seed standard deviation is **1.6–7.7pp** with the passive action
space, against 0.7–1.7pp for the earlier pure-aggressive system. Adding a
second continuous action with a genuine exploration trade-off made
training substantially less stable.

This produced one published error. A single passive run scored +37% and
+13.5%/+15.0% against POV 20% and became the v4 headline. It does not
reproduce: the same model file, config and scripts later scored
−1.7%/−0.3%. Seven mechanical explanations were tested and eliminated
(config drift, dead parameters, evaluation script, model identity, action
dimension, code changes, fee attribution) before the seed study identified
variance as the cause.

The pattern recurred twice more — single-seed evaluations landed above
3-seed means both before and after the permanent-impact change. **Every
headline figure in this document is a 3-seed mean.**

### 4.2 Passive execution: implemented, no measurable gain
Passive orders (second action dimension, maker rebates, side-aware fill
model replacing a placeholder hardcoded for buys) produced results
statistically indistinguishable from pure-aggressive, while quadrupling
training variance. Kept and reported as tested rather than removed: it
adds realism, and the negative result is more informative than silently
reverting.

### 4.3 Dead parameter found
`spread_widening_factor` was measured (~1.69 from 3.5M full-consumption
trades) but appears only in the `MarketConfig` dataclass and is never read
by the simulator. Found because reverting it 1.69 → 2.0 produced
byte-identical results.

---

## 5. Calibrated from real data

| Parameter | Was | Now | Source |
|---|---|---|---|
| `impact_exponent` | 0.6 | 0.65 | 11.75M Lee-Ready-classified trades |
| `permanent_impact_exponent` | 1.0 | 0.18 | 312M trade-horizon observations |
| `gamma_permanent` | 5.0e-5 | 7.57e-6 | re-anchored at 10% participation |
| `avg_spread_bps` | 5.9 | 2.133 | 2yr tick data, two methods agreeing |
| `hawkes_decay` | 0.3 | 0.0132 | ACF of excess activity, 6,409 ticker-days |
| `calm_vol` | 0.0002 | 0.000396 | 2-state GMM on rolling volatility |
| `volatile_vol` | 0.0012 | 0.001092 | same |
| `prob_calm_to_volatile` | 0.02 | 0.0241 | observed transition counts |
| `prob_volatile_to_calm` | 0.05 | 0.0531 | same |
| intraday volume profile | formula | measured | 2yr, per-minute |
| per-ticker ADV | flat 5M | real | per ticker |

---

## 6. Known limitations

### 6.1 Size-scaling parameters are not measurable from tape data
`eta_temporary`, `gamma_permanent` (level), `spread_impact_exp` and
`vol_impact_exp` remain uncalibrated for one structural reason: the public
tape contains only small prints (31 of 10.5M classified trades exceeded
~1% participation), so cost at institutional sizes is unobservable. Three
independent measurements agree that at tape-print sizes cost is set by the
spread crossed, not print size — temporary impact scales at 0.104–0.136
with participation, permanent at 0.157–0.191, and a joint regression puts
the participation coefficient near zero with spread at 0.63–0.71 (R² to
0.89).

`passive_fill_prob` is unmeasurable for a related reason: the tape records
executions, not resting orders that never filled.

### 6.2 Hawkes kernel cannot represent real clustering
ACF 0.51 at lag 1, still 0.24 at lag 60 across 6,409 ticker-days. Real
clustering has long memory; a single-exponential kernel cannot represent
it. The mechanism is also self-referential — driven by the simulated
order's own size, not independent market arrivals.

### 6.3 Structural
- Simulator is synthetic; never trained against replayed real order flow.
- No venue routing, queue position, latency, multi-day or portfolio-level
  execution, or market resilience.
- Spread and volume profile are universe-wide averages, not per-ticker.
- `book_depth_levels` unmeasurable from `tbbo` (top-of-book only).
- `book_replenish_halflife` measurement selects on thin pre-trade
  snapshots, so the fitted 26.5s is reversion, not replenishment.
- Training and evaluation share the same simulator.
- Hyperparameters never swept.

### 6.4 Data exclusions, all on stated criteria
Five tickers for partial venue coverage (ETSY median spread 195.8 bps);
DUK for liquidity (3.8% zero-volume minutes, 206-share median minute, 15x
the sell-cost variance of the other twelve); 5 half trading days per
ticker, identified by date at 1-minute granularity where the separation is
unambiguous and applied to all bar sizes; 1.23% of bars clipped for spread
outliers; tick-rule-classified trades excluded from impact analysis
(51.2% accuracy, indistinguishable from chance).

---

## 7. Engineering

Training throughput improved **5.5x** (359 → 1,985 fps) by profiling
rather than guessing:
- The bottleneck was the `EvalCallback` at ~67% of wall-clock (20 episodes
  x 390 steps every 5,000 training steps, run serially). Reducing
  `eval_freq` 5,000 → 50,000 was the main fix.
- **GPU was slower than CPU** in every configuration (2,944 vs 1,834 fps);
  a [256,256] MLP cannot amortise per-step transfer overhead.
- `SubprocVecEnv` beat `DummyVecEnv`; 16 envs beat 8.
- Backtesting parallelised across evaluation seeds: ~4x (3.5h → 50min).

A 10M-step run is now ~1.6h, down from ~8h. Switching to an off-policy
algorithm (SAC/TD3) would not have helped: sample efficiency converts to
wall-clock only when environment stepping dominates, and it did not.

---

## 8. Suggested framing

> The policy reduces execution cost by 26–31% versus TWAP, VWAP and
> Almgren-Chriss, and by 15–40% versus fixed-rate POV at 5% and 10%
> participation. Figures are means across three independently trained
> policies; training-seed standard deviation is 1.6–7.7 percentage points.
>
> It does **not** beat POV at 20% participation, which has held under every
> configuration tested: linear and concave permanent impact, passive and
> pure-aggressive execution, 1-minute and 10-second decisions, four impact
> magnitudes, every walk-forward fold and every training seed.
>
> The simulator's temporary impact model is validated against 11.75M
> Lee-Ready-classified real trades (exponent 0.65 versus a literature
> reference of ~0.5). Permanent impact was measured across 312M
> observations, found concave (0.16–0.19) rather than the linear form
> originally assumed, and the model corrected — which moved results by less
> than training-seed noise.
>
> Decision frequency was tested at 10-second granularity and produced no
> improvement at 10x the training cost, which argues against tick-level
> decision-making for this problem.
>
> Boundaries: absolute impact magnitude is uncalibrated, and at 5x impact
> the edge narrows to 10–17%. Results are relative comparisons within a
> synthetic simulator, not absolute cost predictions.
