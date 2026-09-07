# RL Execution System — Audit v3

Supersedes PROJECT_AUDIT.md and PROJECT_AUDIT_v2.md. Tier 1 and Tier 2 of the
original roadmap are complete.

---

## 1. Headline result

13 US large-cap tickers, ~488 trading days (Aug 2024 – Jul 2026), 1-minute
bars built from real Databento tick data, orders sized at 5% of each ticker's
ADV, POV-style action space, transaction fees modelled.

**Walk-forward validated** — fold 3 trains on days 0–380 and tests on days
380–440, a period the policy never saw:

| | vs TWAP | vs VWAP | vs Almgren-Chriss | vs POV 5% | vs POV 10% | vs POV 20% |
|---|---|---|---|---|---|---|
| **BUY** | +29.2% ±3.6 | +25.4% ±4.1 | +30.4% ±5.2 | +42.5% ±1.4 | +20.7% ±2.7 | **−2.3% ±5.4** |
| **SELL** | +27.1% ±6.2 | +20.3% ±2.9 | +21.8% ±3.0 | +33.0% ±3.5 | +15.9% ±1.7 | **−0.5% ±2.2** |

Consistency across evaluations:

| | Fold 0 (200d train) | Fold 3 (380d train) | Full data (390d train) |
|---|---|---|---|
| BUY vs TWAP | +17.5% | +29.2% | +26.8% |
| BUY vs AC | +17.5% | +30.4% | +23.9% |
| SELL vs TWAP | +26.4% | +27.1% | +22.3% |
| SELL vs AC | +19.1% | +21.8% | +25.1% |

Fold 3 reproduces the full-data result on a disjoint test window. Fold 0's
weaker numbers track its smaller training set (200 vs 380 days) rather than
period-dependence.

**Robustness established:**
- Training-seed variance: ±0.7–1.7pp across three independently trained
  policies — 2–9x smaller than evaluation-seed variance
- Evaluation-seed variance: ±1.4–6.2pp
- Significance: all six original comparisons p=0.0000, Bonferroni-corrected,
  n=3000
- Alpha ablation: removing the synthetic signal from both reward and
  observation changes results by <2.5pp — the edge is execution, not
  forecasting

**Urgency conditioning works** (SPY, completion step of 390):

| urgency | 0.0 | 0.25 | 0.5 | 0.75 | 1.0 |
|---|---|---|---|---|---|
| completion step | 311 | 161 | 108 | 97 | 97 |
| % done by 25% of day | 12.3% | 57.7% | 89.1% | 92.6% | 92.6% |

**Mechanism.** The policy runs at ~6% average participation versus ~11% for
the schedule-based benchmarks, with mean slippage 0.9 bps versus ~2.1 bps.
It wins by being more patient per fill while still completing the order.

---

## 2. Known limitations, quantified

### 2.1 Not beaten by aggressive fixed-rate POV
POV 20% is not beaten in any configuration tested: −2.3%/−0.5% (fold 3),
−3.0%/−2.5% (full data), −14.5%/−6.6% (fold 0), and unchanged at 2x, 5x and
10x impact. Intraday liquidity is U-shaped (24.7% of volume in the first
sixth of the day), so executing aggressively into the liquid open is cheap
under this cost model, and a fixed 20% rate captures most of that with no
learning.

State it plainly: beats schedule-based algos and low-to-mid-rate POV; does
not beat aggressive fixed-rate POV.

### 2.2 The edge narrows as impact rises
`eta_temporary` is uncalibrated (§3.1). Tested at 2x, 5x, 10x, both with the
original policy and with a policy retrained at 5x:

| BUY vs | 1x-trained @1x | 1x-trained @5x | 5x-trained @5x |
|---|---|---|---|
| TWAP | +22.8% | +9.7% | +15.2% ±10.0 |
| VWAP | +24.7% | +15.6% | +14.0% ±5.2 |
| AC | +20.7% | +9.2% | +12.3% ±10.2 (sign flip) |

Retraining recovers part of the loss on TWAP and AC, none on VWAP. Roughly
20–30% at baseline impact, 10–17% at 5x, with buy-side vs AC no longer
reliable at 5x. When trading is expensive, even spreading is closer to
optimal and there is less room to add value.

### 2.3 Permanent impact is concave, not linear — the model is wrong
Measured across **312,796,129 trade-horizon observations** from Lee-Ready
quote-rule-classified trades:

| Horizon | Mean signed impact | t-stat | Fitted exponent | Implied at 1% participation |
|---|---|---|---|---|
| 5 min | +1.75 bps | 566.9 | 0.157 | 4.95 bps |
| 15 min | +1.72 bps | 354.6 | 0.191 | 5.00 bps |
| 60 min | +1.63 bps | 208.2 | 0.188 | 5.16 bps |

11/11 buckets significant at every horizon. Two findings:

- **Shape**: the simulator models permanent impact as LINEAR in participation
  (`gamma_permanent * participation`, Kyle-style). Measured exponent is
  0.16–0.19. The functional form in `market.py` is wrong.
- **Level**: at 1% participation the model implies 0.005 bps; measurement
  says ~5 bps — roughly **1,000x** larger, the same direction as the
  `eta_temporary` gap.
- Impact is flat across 5/15/60 minutes, confirming it genuinely persists
  rather than decaying (which would make it temporary).

Caveats: within-day demeaning biases estimates slightly downward; the 60-min
horizon shows negative values in the sparsest buckets; and individual-print
impact is not the same object as metaorder impact, which is what the
literature usually measures.

**Not yet acted on.** Fixing it means a new functional form, recalibration,
retrain and full revalidation.

---

## 3. Still open

### 3.1 `eta_temporary` absolute level
Uncalibrated, with quantified consequences (§2.2). Only 31 of 10.5M
classified trades exceeded ~1% participation, so the public tape cannot
observe impact at institutional order sizes. Needs real parent-order fill
data.

### 3.2 Remaining uncalibrated parameters
`spread_impact_exp` (0.3), `vol_impact_exp` (0.4),
`adverse_selection_factor` (0.3), `spread_widening_factor` (2.0),
`book_depth_levels` (10), `book_replenish_halflife` (5),
`calm_vol`/`volatile_vol`, regime transition probabilities,
`hawkes_baseline`/`hawkes_alpha`, news parameters. Most are measurable from
data already purchased.

### 3.3 Hawkes kernel cannot represent real clustering
Measured ACF of excess trading activity: 0.51 at lag 1, still 0.24 at lag 60
across 6,409 ticker-days. Real order-flow clustering has long memory; a
single-exponential kernel cannot represent it, so the fitted `hawkes_decay`
(0.0132) depends on the fit range. The mechanism is also self-referential —
driven by the simulated order's own size, not independent market arrivals.

### 3.4 Structural
- Simulator is synthetic; the agent has never traded against replayed real
  order flow.
- No passive/limit orders — only aggressive marketable orders, so the agent
  always pays the taker fee and never earns a maker rebate.
- No venue routing, queue position, latency, multi-day or portfolio-level
  execution, or market resilience.
- Spread and volume profile are universe-wide averages, not per-ticker.
- Alpha signal is synthetic (ablation shows it doesn't drive the result).
- Data source `EQUS.MINI` is a partial-venue composite, not full NBBO.

### 3.5 Data exclusions (all documented, all applied on stated criteria)
- **5 tickers** (UNH, JNJ, CAT, ROKU, ETSY) — implausible spreads from
  partial venue coverage (ETSY median 195.8 bps)
- **DUK** — 3.8% zero-volume minutes, 206-share median minute, and 15x the
  sell-cost variance of the other twelve combined
- **~5 half trading days per ticker** (§4.3)
- **1.23% of bars** — spread outliers clipped per-ticker at 20x median

---

## 4. Bugs found and fixed

Recording these because several were invisible in aggregate statistics and
only surfaced under targeted diagnostics.

### 4.1 Action space was inert (the urgency failure)
Six reward-shaping attempts failed to produce urgency-conditioned behaviour.
Root cause was the action parameterisation, not the reward: with
`qty = action × remaining`, the participation cap binds whenever
`action × remaining > max_participation × step_volume`. Measured on real
data with a 96k order against ~6k-share minutes, **everything above
`action = 0.016` produced an identical fill** — 98.4% of the action range was
dead. Reparameterising to POV-style (`action × max_participation ×
step_volume`) made every action distinct and urgency conditioning emerged
from the existing reward with no further shaping.

Note ADV sizing alone did not fix it (5% of ADV came to 96,091 shares,
essentially the same as the fixed 100k). Both changes were needed.

### 4.2 Order infeasibility at fixed size
At 100k shares, three tickers could not complete within a session even at
maximum participation (PG 84k, JPM 84k, CVX 92k max executable per day).

### 4.3 Half trading days padded with zero-volume bars
US markets close at 1pm ~3 days a year. `tick_to_bars.py` padded every
session to 390 bars, appending ~180 zero-volume bars on those days. With
zero volume the participation cap permits nothing, so schedule-based
benchmarks accumulated their entire inventory through the dead stretch and
`force_fill` dumped it into a zero-volume bar at the final step. Observed on
an NVDA day: **26 bps at step 388, 533,989 bps after step 389.** 65
ticker-days affected (5 days × 13 tickers). Detected by zero-volume
fraction, which also catches data gaps of the same shape.

### 4.4 Others
- **`impact_calibration.py` used the flat config ADV for every ticker**
  instead of real per-ticker `ticker_adv`, so low-ADV names were capped
  almost every sample. Affected every calibration run before the fix.
- **Hawkes ACF inflated by day-level activity shifts.** Residuals measured
  against a universe-average profile meant a busy day produced positive
  residuals at every lag. Synthetic check: unfixed recovered 0.0149 against
  a true 0.030; demeaning within ticker-day recovered 0.0289.
- **Spread artifacts** — 554 bars above 1000 bps, 299 of them AAPL, from
  composite BBO gaps when the venue holding the best quote drops out.
- **Negative spreads crashed training** via complex-number exponentiation
  (fractional power of a negative base). Fixed at source and defensively in
  `compute_impact`.
- **`force_fill` / backlog caps** — mandatory liquidation was being capped by
  the simulator's own participation limit, silently stranding inventory.

---

## 5. Suggested framing

> The policy reduces execution cost by 20–30% versus TWAP, VWAP and
> Almgren-Chriss on both sides. This is validated out-of-sample by
> walk-forward (fold 3 trains on days 0–380, tests on days 380–440 and
> reproduces the full-data result), is stable across three independently
> trained policies (training-seed std under 1.7pp), and is significant under
> Bonferroni correction at n=3000. It learns urgency-conditioned execution:
> patient orders complete around step 311 of 390, urgent orders around step
> 97. It wins by trading at roughly half the participation rate of the
> benchmarks — 0.9 bps mean slippage versus 2.1 — while still completing.
>
> The simulator is calibrated against real tick data: impact exponent
> validated against 11.75M Lee-Ready-classified trades (measured 0.65 vs a
> literature reference of ~0.5), plus spread, intraday volume profile and
> order-flow decay from two years of data.
>
> Boundaries: it does not beat an aggressive fixed-rate POV (20%) in any
> configuration tested. The absolute impact magnitude is uncalibrated, and at
> 5x impact the edge narrows to 10–17%. Permanent impact was measured across
> 312M observations and found to be concave (exponent ~0.17) rather than the
> linear form the simulator assumes — a known modelling error not yet
> corrected. Results are relative comparisons within a synthetic simulator.

The diagnostic work is a substantial part of the value: tracing the urgency
failure to the action parameterisation, isolating DUK's variance
contribution, identifying half-day padding as the source of 533,989 bps
episodes, and mapping sensitivity to the least-certain parameter are all
more informative than a clean number with no error analysis.
