# RL Execution System — Audit v5

Supersedes PROJECT_AUDIT_v4.md.

**v4 is withdrawn.** It reported +37% versus schedule-based benchmarks and
claimed POV 20% was beaten by 13-15%. Both figures came from a single
training run and do not reproduce. A three-seed study on the same
configuration establishes the correct numbers below. v4 also listed
`spread_widening_factor` as calibrated; the simulator never reads it.

---

## 1. Headline result

**13 US large-cap tickers, ~488 trading days each (Aug 2024 – Jul 2026),
1-minute bars, orders at 5% of each ticker's ADV, POV-style action space
with passive/aggressive split, fees and rebates modelled.**

Mean across **three independently trained policies**, each evaluated at
1,000 episodes:

| | vs TWAP | vs VWAP | vs Almgren-Chriss |
|---|---|---|---|
| **BUY** | +25.5% ± 4.9% | +27.1% ± 4.8% | +26.0% ± 4.9% |
| **SELL** | +23.0% ± 1.0% | +18.1% ± 5.3% | +21.5% ± 1.6% |

| | vs POV 5% | vs POV 10% | vs POV 20% |
|---|---|---|---|
| **BUY** | +36.8% ± 4.1% | +19.8% ± 5.3% | **−2.5% ± 6.7%** ⚠ sign flip |
| **SELL** | +30.6% ± 6.2% | +9.0% ± 2.8% | **−9.0% ± 1.1%** |

**POV 20% is not beaten.** No training seed beat it; the sell side lost by
8-10% on every one. This has held across every fold, impact level,
configuration and seed tested.

Quote error bars as ± the training-seed standard deviation, not the
evaluation-seed one. See §3.1.

---

## 2. Validation

**Walk-forward.** Fold 3 trains on days 0–380 and tests on days 380–440 —
never seen — and reproduced the full-sample result at the time it was run.
Fold 0's weaker numbers track its smaller training set (200 days), not
period dependence.

**Statistical significance.** All six schedule-benchmark comparisons
p=0.0000, Bonferroni-corrected, n=3000 (measured pre-passive).

**Alpha ablation.** Removing the synthetic forecasting signal from both the
reward and the observation changes results by under 2.5pp. The improvement
is execution scheduling, not forecasting.

**Impact-magnitude sensitivity.** `eta_temporary` is uncalibrated. Tested
at 1x/2x/5x/10x including a retrain at 5x: the edge narrows from ~20–30%
to 10–17%, and buy-side vs Almgren-Chriss becomes unreliable at 5x.

---

## 3. Passive execution: implemented, no measurable gain

Passive orders were added (second action dimension splitting each step
between resting at the touch and crossing the spread), with maker rebates
and a side-aware fill model replacing a placeholder that was hardcoded for
buys.

**Result: performance is statistically indistinguishable from the
pure-aggressive system.**

| | Pre-passive | Passive (3-seed mean) |
|---|---|---|
| BUY vs TWAP | +26.9% | +25.5% |
| BUY vs AC | +25.8% | +26.0% |
| BUY vs POV20 | −2.3% | −2.5% |
| SELL vs TWAP | +24.8% | +23.0% |

### 3.1 Training variance quadrupled
Pre-passive training-seed std was **0.7–1.7pp**. With the passive action
dimension it is **4.8–6.7pp** on the buy side. Adding a second continuous
action with a genuine exploration trade-off (rest and maybe not fill
versus cross and pay) made training substantially less stable.

This caused a real error. One passive training run scored +37% against
schedule benchmarks and +13.5%/+15.0% against POV 20%, and was written up
as the headline in v4. It was a favourable draw from a wider distribution
and does not reproduce: the same model file, same config and same scripts
now score −1.7%/−0.3% on POV 20%. Seven mechanical explanations were
tested and eliminated (config drift, dead parameters, evaluation script,
model file identity, action-space dimension, code changes, fee
attribution) before the seed study identified variance as the cause.

**Lesson: never quote a single training run.** The pre-passive system's
tight seed variance made single runs look trustworthy; that property did
not survive the action-space change.

### 3.2 The sensitivity sweep was a missed warning
`passive_fill_prob` was swept 0.1 → 0.5 and results moved under 1.5pp;
setting the maker rebate to zero changed nothing. This was read as
robustness. In hindsight it indicated the mechanism was not doing much —
a component insensitive to its own key parameters is a component with
little influence.

### 3.3 Whether to keep it
Kept, and reported as implemented-and-tested rather than removed. It adds
realism (real desks work the passive side heavily) and the negative result
is more informative than silently reverting. Costs: an extra uncalibrated
parameter, a more complex action space, and 4x training variance.

---

## 4. Calibrated from real data

| Parameter | Was | Now | Source |
|---|---|---|---|
| `impact_exponent` | 0.6 | 0.65 | 11.75M Lee-Ready-classified trades |
| `avg_spread_bps` | 5.9 | 2.133 | 2yr tick data, two methods agreeing |
| `hawkes_decay` | 0.3 | 0.0132 | ACF of excess activity, 6,409 ticker-days |
| `calm_vol` | 0.0002 | 0.000396 | 2-state GMM on rolling volatility |
| `volatile_vol` | 0.0012 | 0.001092 | same |
| `prob_calm_to_volatile` | 0.02 | 0.0241 | observed transition counts |
| `prob_volatile_to_calm` | 0.05 | 0.0531 | same |
| intraday volume profile | formula | measured | 2yr, per-minute |
| per-ticker ADV | flat 5M | real | per ticker |

**`spread_widening_factor` was measured (~1.69 from 3.5M full-consumption
trades) but is a DEAD PARAMETER** — it appears only in the `MarketConfig`
dataclass declaration and is never read by the simulator. Reverting it
from 1.69 to 2.0 produced byte-identical results, which is how this was
found. The measurement stands; it simply feeds nothing.

---

## 5. Known limitations

### 5.1 Permanent impact is the wrong functional form
Measured over **312M observations**: exponent 0.157/0.191/0.188 at
5/15/60 min against the simulator's assumed **1.0**, and ~5 bps at 1%
participation against the model's 0.005 bps. Both shape and level wrong.
11/11 buckets significant at every horizon. **Not corrected.**

### 5.2 Size-scaling parameters are not measurable from tape data
`eta_temporary`, `gamma_permanent`, `spread_impact_exp` and
`vol_impact_exp` all remain uncalibrated for the same structural reason:
the public tape contains only small prints (31 of 10.5M classified trades
exceeded ~1% participation), so cost at institutional sizes is
unobservable. Three independent measurements agree that at tape-print
sizes cost is set by the spread crossed, not the size of the print —
temporary impact scales at 0.104–0.136 with participation, permanent at
0.157–0.191, and a joint regression puts the participation coefficient at
approximately zero with spread at 0.63–0.71 (R² up to 0.89).

`passive_fill_prob` is unmeasurable for a related reason: the tape records
executions, not resting orders that never filled.

### 5.3 Hawkes kernel cannot represent real clustering
ACF 0.51 at lag 1, still 0.24 at lag 60 across 6,409 ticker-days. Real
clustering has long memory; a single-exponential kernel cannot represent
it. The mechanism is also self-referential — driven by the simulated
order's own size, not independent market arrivals.

### 5.4 Structural
- Simulator is synthetic; never trained against replayed real order flow.
- No venue routing, queue position, latency, multi-day or portfolio-level
  execution, or market resilience.
- Spread and volume profile are universe-wide averages, not per-ticker.
- `book_depth_levels` unmeasurable from `tbbo` (top-of-book only).
- `book_replenish_halflife` measurement attempted but the sample selects
  on thin pre-trade snapshots, so the fitted 26.5s is reversion, not
  replenishment. The profile does suggest recovery is far faster than the
  configured 5 steps (300s).
- Training and evaluation share the same simulator — no out-of-model
  validation.
- Hyperparameters never swept; reward weights other than alpha never
  ablated.

### 5.5 Data exclusions, all on stated criteria
Five tickers for partial venue coverage (ETSY median spread 195.8 bps);
DUK for liquidity (3.8% zero-volume minutes, 206-share median minute, 15x
the sell-cost variance of the other twelve); ~5 half trading days per
ticker; 1.23% of bars clipped for spread outliers; tick-rule-classified
trades excluded from impact analysis (51.2% accuracy, indistinguishable
from chance).

---

## 6. Engineering

Training throughput improved **5.5x** (359 → 1,985 fps) by profiling
rather than guessing:
- The bottleneck was the `EvalCallback`, consuming ~67% of wall-clock
  (20 episodes x 390 steps every 5,000 training steps, run serially).
  Reducing `eval_freq` 5,000 → 50,000 was the main fix.
- **GPU was slower than CPU** in every configuration (2,944 vs 1,834 fps).
  A [256,256] MLP cannot amortise per-step transfer overhead.
- `SubprocVecEnv` beat `DummyVecEnv`; 16 envs beat 8.
- Backtesting parallelised across evaluation seeds: ~4x (3.5h → 50min).

A 10M-step run is now ~1.6h, down from ~8h. Switching to an off-policy
algorithm (SAC/TD3) would not have helped: sample efficiency converts to
wall-clock only when environment stepping dominates, and it did not.

---

## 7. Suggested framing

> The policy reduces execution cost by 18–27% versus TWAP, VWAP and
> Almgren-Chriss, and by 9–37% versus fixed-rate POV at 5% and 10%
> participation. Figures are means across three independently trained
> policies; training-seed standard deviation is 1.0–6.7 percentage points.
>
> It does **not** beat POV at 20% participation, which has held across
> every fold, impact level, configuration and training seed tested. Under
> this cost model, aggressive fixed-rate participation is hard to beat,
> because intraday liquidity is U-shaped and executing into the liquid
> open is genuinely cheap.
>
> Passive order placement was implemented and tested and produced no
> measurable improvement, while quadrupling training variance.
>
> The simulator's temporary impact model is validated against 11.75M
> Lee-Ready-classified real trades (measured exponent 0.65 versus a
> literature reference of ~0.5), with spread, volume profile, volatility
> regimes and order-flow decay calibrated from two years of tick data.
> Permanent impact was measured across 312M observations and found concave
> (0.16–0.19) rather than the linear form the simulator assumes — a known,
> uncorrected discrepancy.
>
> Boundaries: absolute impact magnitude is uncalibrated, and at 5x impact
> the edge narrows to 10–17%. Results are relative comparisons within a
> synthetic simulator, not absolute cost predictions.

The diagnostic record is a substantial part of the value: tracing the
urgency failure to an inert action space, isolating DUK's 15x variance
contribution, identifying the venue-coverage problem, catching half
trading days via a 533,989 bps outlier, finding a dead config parameter
through byte-identical results, and — after eliminating seven mechanical
explanations — identifying training variance as the reason a headline
figure failed to reproduce.
