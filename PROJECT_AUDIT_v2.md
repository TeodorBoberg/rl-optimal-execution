# RL Execution System — Audit v2

Supersedes PROJECT_AUDIT.md. Updated after completing Tier 1 and most of
Tier 2 of the original roadmap.

---

## Current headline result

**Baseline impact level (`eta_temporary = 0.0005`), 13 tickers, 2 years of
1-minute bars, orders at 5% of each ticker's ADV, POV-style action space:**

| | vs TWAP | vs VWAP | vs Almgren-Chriss | vs POV 5% | vs POV 10% | vs POV 20% |
|---|---|---|---|---|---|---|
| **BUY** | +27.2% | +25.3% | +25.0% | +34.1% | +16.8% | **−4.9%** ⚠ |
| **SELL** | +27.7% | +20.5% | +24.9% | +34.9% | +16.2% | **+0.4%** ⚠ |

All six original comparisons significant at p=0.0000, Bonferroni-corrected,
n=3000. Evaluation-seed std 2.7–9.0pp; **training-seed std 0.7–1.7pp** across
three independently trained policies.

⚠ POV 20% is not beaten at any tested impact level. See §2.

**Urgency conditioning works.** Completion step responds monotonically:

| SPY | urgency 0.0 | 0.25 | 0.5 | 0.75 | 1.0 |
|---|---|---|---|---|---|
| completion step | 311 | 161 | 108 | 97 | 97 |
| % done by 25% of day | 12.3% | 57.7% | 89.1% | 92.6% | 92.6% |

---

## 1. Resolved since v1

**Urgency conditioning (was §1.4, the largest open limitation).** Six reward-
shaping attempts failed. Root cause was neither the reward nor the order size
but the **action parameterisation**: with `qty = action × remaining`, the
participation cap binds whenever `action × remaining > max_participation ×
step_volume`. Measured: with a 96k order against ~6k-share minutes, everything
above `action = 0.016` produced an identical fill — 98.4% of the action range
was dead. Reparameterising to `qty = action × max_participation × step_volume`
(POV-style) made every action value distinct, and urgency conditioning emerged
from the existing reward with no further shaping.

Note ADV sizing alone did **not** fix this — 5% of ADV came to 96,091 shares on
the test case, essentially identical to the fixed 100k. Both changes were
needed: POV actions for a live action space, ADV sizing for feasible orders.

**Order feasibility (was §2.5).** At a fixed 100k shares, three tickers
(PG 84k, JPM 84k, CVX 92k max executable per day) could not complete the order
within a session even at maximum participation. Orders are now 5% of each
ticker's ADV — 16.8k (PG) to 366k (NVDA).

**Training-seed variance (was §6.1, "the most-asked-about gap").** Three
independently trained policies: std 0.7–1.7pp per comparison, no sign flips.
Training variance is **2–9x smaller** than evaluation variance. The improvement
is a property of the method, not of one training run.

**Data window (was §2.2).** 78 days → **493 days per ticker** (Aug 2024 – Jul
2026), 2,499,510 bars, ~$64 of Databento credit. Quote quality improved: all 13
tickers pass the reliability threshold with margin (worst: JPM 5.26bps median
vs a 20bps cutoff), versus 13-of-14 on the short window.

**Recalibrated on 2-year data (was §3):** `avg_spread_bps` 5.9 → **2.133**
(triangulated across raw-tick and bar-level medians), `hawkes_decay` 0.3 →
**0.0132**, intraday volume profile regenerated (24.7% / 15.6% / 12.0% / 10.9%
/ 11.2% / 25.6% by sixth of day).

**POV benchmarks added (was §6.3).** Three fixed rates (5/10/20%). This is the
most relevant family, since the agent is now itself a learned POV algo.

---

## 2. New findings

### 2.1 POV 20% is not beaten, and this is robust
RL vs POV 20%: −4.9% buy / +0.4% sell at baseline impact; −3.6% / +11.6% at
10x impact; −4.4% / +4.0% when *retrained* at 5x. The result does not move.

Mechanism: intraday liquidity is U-shaped (24.7% of volume in the first sixth
of the day), so executing aggressively into the liquid open is genuinely cheap
under this cost model. A fixed 20% participation rate captures most of that
advantage with no learning at all. The agent runs at ~6.2% average
participation and completes around step 90–110.

This should be disclosed, not buried. "Beats schedule-based algos and low-to-
mid-rate POV; does not beat aggressive fixed-rate POV" is the accurate claim.

### 2.2 The edge shrinks as impact rises
Because `eta_temporary` is uncalibrated, the result was tested at 2x, 5x and
10x, both with the original policy and with a policy **retrained** at 5x:

| BUY vs | 1x-trained @1x | 1x-trained @5x | 5x-trained @5x |
|---|---|---|---|
| TWAP | +22.8% | +9.7% | +15.2% ± 10.0% |
| VWAP | +24.7% | +15.6% | +14.0% ± 5.2% |
| AC | +20.7% | +9.2% | +12.3% ± 10.2% ⚠ sign flip |

Retraining recovers part of the loss on TWAP and AC, none on VWAP. So training
mismatch explains **some** of the erosion, not most. The honest reading: when
trading is expensive, spreading evenly is closer to optimal and there is less
room for a smarter policy to add value. Roughly 20–27% at baseline impact,
10–17% at 5x, with buy-side vs AC no longer reliable at 5x.

### 2.3 Real order-flow clustering has long memory
With 6,409 ticker-days, the autocorrelation of excess trading activity is
clearly **not exponential** — 0.51 at lag 1, still 0.24 at lag 60. A single-
exponential Hawkes kernel cannot represent this, so the fitted `hawkes_decay`
depends on the chosen fit range. Better evidenced than in v1.

### 2.4 Bugs found and fixed
- **`impact_calibration.py` used the flat config ADV for every ticker** instead
  of the real per-ticker `ticker_adv`, so low-ADV names were capped almost
  every sample. Affected every calibration run prior to the fix.
- **Hawkes ACF was inflated by day-level activity shifts.** Residuals were
  measured against a universe-average profile, so a busy day produced positive
  residuals at every lag. Verified on synthetic data: the unfixed version
  recovered 0.0149 against a true 0.030; demeaning within ticker-day recovered
  0.0289. Negligible at 78 days, dominant at 493.
- **Spread artifacts in EQUS.MINI.** 554 bars exceeded 1000bps, 299 of them
  AAPL. Partial-venue composite BBO goes absurdly wide when the venue holding
  the best quote drops out. Clipped per-ticker at 20x median (1.23% of bars).
- **Negative spreads crashed training** via complex-number exponentiation.
  Fixed at source (per-tick spread median rather than independent bid/ask
  medians) and defensively in `compute_impact`.
- **`force_fill` / backlog-aware caps.** Mandatory liquidation was being capped
  by the simulator's own participation limit, silently stranding inventory —
  the original position-cap bug resurfacing at finer granularity.

---

## 3. Still open

### 3.1 `eta_temporary` absolute level — now with quantified consequences
Still uncalibrated. §2.2 shows this parameter determines whether the edge is
~25% or ~13%, and whether buy-side vs AC is a win at all. The public tape
cannot observe impact at institutional participation rates (31 of 10.5M
classified trades exceeded ~1% participation). Needs real parent-order fill
data.

### 3.2 `gamma_permanent` — never validated
Neither shape nor level. Measurable in principle from the tick data already
purchased: price level 5/15/60 minutes after a classified trade versus
pre-trade mid, by trade size.

### 3.3 Remaining uncalibrated parameters
`spread_impact_exp` (0.3), `vol_impact_exp` (0.4), `adverse_selection_factor`
(0.3), `spread_widening_factor` (2.0), `book_depth_levels` (10),
`book_replenish_halflife` (5), `calm_vol`/`volatile_vol`, regime transition
probabilities, `hawkes_baseline`/`hawkes_alpha`, news parameters. Most are
measurable from existing data — likely the best value-per-hour work left.

### 3.4 Structural, unchanged from v1
- Simulator is synthetic; the agent has never traded against replayed real
  order flow.
- Hawkes mechanism is self-referential (driven by the simulated order's own
  size, not independent market arrivals).
- Alpha signal is synthetic (ground-truth forward return plus noise).
- No fees, no passive/limit orders, no venue routing, no queue position, no
  latency, no multi-day or portfolio-level execution, no market resilience.
- Spread and volume profile are universe-wide averages, not per-ticker.
- Six of nineteen tickers excluded on documented criteria (five for quote
  coverage, DUK for liquidity: 3.8% zero-volume minutes, 206-share median
  minute, and 15x the sell-cost variance of all other tickers combined).

### 3.5 Roadmap items not yet done
- **#8 Reward ablation** — which terms actually matter? Especially removing the
  synthetic alpha signal to isolate pure execution skill.
- **#9 Walk-forward validation** — currently one chronological split, no rolling
  retraining. Now feasible with 493 days.
- **#10 Transaction fees and rebates.**
- **#6 Permanent impact measurement** (see §3.2).

---

## 4. Suggested framing

> The policy improves execution cost by 20–27% versus TWAP, VWAP and
> Almgren-Chriss on both sides, statistically significant under Bonferroni
> correction (n=3000), stable across evaluation seeds and across three
> independently trained policies (training-seed std under 1.7pp). It learns
> urgency-conditioned behaviour: patient orders complete around step 311 of
> 390, urgent orders around step 97.
>
> The simulator's impact model is validated against 11.75M real trades
> classified with Lee-Ready — measured exponent 0.65 against a literature
> reference of ~0.5. Spread, intraday volume profile and order-flow decay are
> calibrated from two years of real tick data.
>
> Boundaries of the result: the absolute impact magnitude is uncalibrated, and
> at 5x impact the edge narrows to 10–17% with buy-side vs Almgren-Chriss no
> longer reliable. The policy does not beat an aggressive fixed-rate POV (20%)
> at any tested impact level. Results are relative comparisons within a
> synthetic simulator, not absolute cost predictions.

The diagnostic work is a substantial part of the value. Identifying the
venue-coverage problem, isolating DUK's variance contribution, tracing the
urgency failure to the action parameterisation, and mapping the result's
sensitivity to its least-certain parameter are all more informative than a
clean number with no error analysis.
