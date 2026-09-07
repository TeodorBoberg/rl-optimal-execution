# RL Execution System — Audit v7

Supersedes v6. Adds the reward-term ablation study.

---

## 1. Headline result

13 US large-cap tickers, 488 trading days (Aug 2024 – Jul 2026), 1-minute
bars, orders at 5% of each ticker's ADV, POV action space with
passive/aggressive split, fees and rebates, concave permanent impact.

**Mean across three independently trained policies**, 1,000 episodes each:

| | vs TWAP | vs VWAP | vs Almgren-Chriss |
|---|---|---|---|
| **BUY** | +28.5% ± 5.2% | +30.1% ± 5.1% | +30.6% ± 5.0% |
| **SELL** | +28.4% ± 1.9% | +26.2% ± 1.6% | +29.0% ± 4.7% |

| | vs POV 5% | vs POV 10% | vs POV 20% |
|---|---|---|---|
| **BUY** | +39.6% ± 4.4% | +23.3% ± 5.6% | **−5.8% ± 7.7%** ⚠ |
| **SELL** | +38.2% ± 3.0% | +15.4% ± 4.9% | **+0.3% ± 4.8%** ⚠ |

Error bars are training-seed standard deviations. Never quote a single run
(§4.1). **POV 20% is not beaten** under any configuration tested.

**Urgency conditioning works**: SPY completion step 311 → 97 as urgency
goes 0.0 → 1.0; 12.3% → 92.6% of the order done by the quarter mark.

---

## 2. Reward-term ablation study

Seven of eight reward terms had never been tested. All were hand-tuned
reactively while debugging other problems. Each ablation is a full retrain
plus 3-seed evaluation.

| Term | Verdict | Effect of removing |
|---|---|---|
| `hold` | **Load-bearing** | −6 to −12 pts, uniformly across all 12 comparisons |
| `pacing` | **Trades performance for a feature** | +1 to +8 pts, tighter error bars, POV20 sign flips resolved — **but urgency conditioning dies completely** |
| `impact` | Neutral | ~0, error bars widen slightly |
| `regime` | Neutral | ~0 |
| `news` | Neutral | ~0 |
| `adverse_selection` | Neutral | ~0 |
| `trade` | Not tested | Zeroing removes any incentive to trade; foregone conclusion |
| `alpha` | Neutral (tested earlier) | <2.5 pts |

**Four of eight terms do nothing.** They can be removed to simplify the
reward and shrink the tuning surface, though doing so has not been
validated in combination.

### 2.1 The pacing trade-off
Removing `pacing` improves all twelve comparisons and tightens variance:

| | With pacing | Without pacing |
|---|---|---|
| BUY vs TWAP | +28.5% ± 5.2% | +34.2% ± 4.0% |
| SELL vs AC | +29.0% ± 4.7% | +36.4% ± 4.5% |
| BUY vs POV20 | −5.8% (sign flip) | **+2.1% ± 2.0%** |
| Urgency conditioning | **works** | **dead — flat at every level** |

Without pacing the policy reverts to a single fixed schedule regardless of
the urgency input: identical completion step, fill profile and cost at
urgency 0.0 and 1.0, on all three tickers tested.

This corrects an earlier reading that pacing had become redundant once the
action space was reparameterised. The POV reparameterisation made urgency
conditioning *possible*; pacing is what makes it *happen*. Both are
required.

The trade-off is economically coherent rather than a defect: urgency
conditioning means deliberately trading sub-optimally when instructed to be
patient, so enforcing it necessarily costs performance. **Measured price of
the urgency feature: 5–8 percentage points and wider training variance.**

Current default keeps pacing. Both configurations are defensible.

---

## 3. Validation

**Walk-forward.** Fold 3 trains on days 0–380, tests on days 380–440 —
never seen — and reproduced the full-sample result.

**Statistical significance.** All six schedule-benchmark comparisons
p=0.0000, Bonferroni-corrected, n=3000.

**Alpha ablation.** Removing the synthetic forecasting signal from reward
and observation changes results <2.5 pts. The improvement is execution
scheduling, not forecasting.

**Impact-magnitude sensitivity.** `eta_temporary` uncalibrated; tested at
1x/2x/5x/10x with a retrain at 5x. Edge narrows to 10–17% at 5x.

**Passive-assumption sensitivity.** `passive_fill_prob` swept 0.1 → 0.5,
maker rebate set to zero: results moved <1.5 pts.

**Decision frequency.** 10-second bars (2,340 steps/day, 14.8M bars, 17h
training vs 1.6h) produced no improvement. See §5.2.

---

## 4. Methodological findings

### 4.1 Single training runs are unreliable
Training-seed std is 1.6–7.7 pts. One passive run scored +37% and
+13.5%/+15.0% against POV 20% and became the v4 headline; it does not
reproduce (same model, config and scripts later gave −1.7%/−0.3%). Seven
mechanical explanations were eliminated before the seed study identified
variance as the cause. The pattern recurred twice more. **Every figure in
this document is a 3-seed mean.**

Note the earlier attribution of elevated variance to the passive action
dimension is only partly right — the pacing penalty contributes, since it
penalises deviation from a schedule while the cost model rewards it,
leaving the policy optimising two partly-opposed objectives.

### 4.2 Passive execution: implemented, no measurable gain
Statistically indistinguishable from pure-aggressive while quadrupling
training variance. Kept and reported as tested; the negative result is more
informative than silently reverting.

### 4.3 Dead parameter
`spread_widening_factor` was measured (~1.69 from 3.5M full-consumption
trades) but appears only in the `MarketConfig` dataclass and is never read.
Found because reverting it 1.69 → 2.0 gave byte-identical results.

---

## 5. Model corrections

### 5.1 Permanent impact
Assumed linear (`gamma * participation`, Kyle 1985). Measured over **312M
classified trade observations**: exponent 0.157/0.191/0.188 at 5/15/60 min,
11/11 buckets significant at every horizon, flat across horizons
(confirming genuinely permanent).

Now `gamma * participation ** 0.18`, with `gamma_permanent` re-anchored
5.0e-5 → 7.57e-6 so impact at 10% participation matches the previous model.
The measured **level** was deliberately not imported: observations sit at
~0.002% participation while the simulator operates at 5–25%, and
extrapolating across that gap is the error that produced an implausible
868x value for `eta_temporary`.

Effect: +3 to +5 pts, within one standard deviation. Fixing the largest
known modelling error moved results by less than seed noise.

Concavity penalises **fragmentation**, not size: it charges 43x more at
0.1% participation and 6.6x more at 1%, so strategies spreading many tiny
fills across thin bars are hit hardest.

### 5.2 Decision frequency: no benefit at 10 seconds
Only POV20 gave valid statistics at both frequencies:

| | 1-minute | 10-second |
|---|---|---|
| BUY vs POV20 | −2.5% | −26.8% |
| SELL vs POV20 | −9.0% | +6.9% |

No consistent improvement at 10x the training cost. With the
credit-assignment problem at longer horizons (a tick-level episode would
need `gamma` ≈ 0.99998), this argues against tick-level decision-making.

### 5.3 Schedule-based benchmarks break at fine granularity
At 2,340 steps a fixed-schedule strategy targets 1/2340th per bar, but
10-second bars are frequently empty (median 9.6% zero-volume, max 72.2%).
Schedule algos accumulate backlog and hit `force_fill`:

| Strategy | Max participation | Max episode cost |
|---|---|---|
| POV5 sell | **26.18** | **28,043 bps** |
| TWAP buy | 8.30 | 6,538 bps |
| **RL agent** | **0.11 / 0.15** | 292 / 379 bps |

The agent degrades gracefully because its POV action scales with actual bar
volume. **A real argument for volume-based over schedule-based execution**,
independent of any RL result. The 10-second comparisons against TWAP, VWAP,
AC, POV5 and POV10 measure benchmark breakdown and must not be quoted.

---

## 6. Calibrated from real data

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

## 7. Known limitations

**Size-scaling parameters are not measurable from tape data.**
`eta_temporary`, `gamma_permanent` (level), `spread_impact_exp` and
`vol_impact_exp` remain uncalibrated: the tape contains only small prints
(31 of 10.5M classified trades exceeded ~1% participation). Three
independent measurements agree that at tape-print sizes cost is set by the
spread crossed, not print size. `passive_fill_prob` is unmeasurable for a
related reason — the tape records executions, not resting orders that never
filled.

**Hawkes kernel cannot represent real clustering.** ACF 0.51 at lag 1,
still 0.24 at lag 60 across 6,409 ticker-days. Long memory; a
single-exponential kernel cannot represent it. The mechanism is also
self-referential, driven by the simulated order's own size.

**Structural.** Synthetic simulator, never trained against replayed real
order flow. No venue routing, queue position, latency, multi-day or
portfolio-level execution, or market resilience. Spread and volume profile
are universe-wide averages. `book_depth_levels` unmeasurable from `tbbo`.
Training and evaluation share the same simulator. Hyperparameters never
swept.

**Data exclusions, all on stated criteria.** Five tickers for partial venue
coverage (ETSY median spread 195.8 bps); DUK for liquidity (3.8%
zero-volume minutes, 15x the sell-cost variance of the other twelve); 5
half trading days per ticker, identified by date at 1-minute granularity
and applied to all bar sizes; 1.23% of bars clipped for spread outliers;
tick-rule-classified trades excluded from impact analysis (51.2% accuracy,
indistinguishable from chance).

---

## 8. Engineering

Training throughput improved **5.5x** (359 → 1,985 fps) by profiling:
- Bottleneck was the `EvalCallback` at ~67% of wall-clock. Reducing
  `eval_freq` 5,000 → 50,000 was the main fix.
- **GPU was slower than CPU** in every configuration (2,944 vs 1,834 fps);
  a [256,256] MLP cannot amortise per-step transfer overhead.
- `SubprocVecEnv` beat `DummyVecEnv`; 16 envs beat 8.
- Backtesting parallelised across seeds: ~4x (3.5h → 50min).

A 10M-step run is now ~1.6h, down from ~8h. Off-policy algorithms
(SAC/TD3) would not have helped: sample efficiency converts to wall-clock
only when environment stepping dominates, and it did not.
