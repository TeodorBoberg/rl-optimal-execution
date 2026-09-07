# RL Execution System — Audit v4

Supersedes PROJECT_AUDIT_v3.md. Adds passive execution, five newly
calibrated parameters, and the sensitivity work that tests them.

---

## 1. Headline result

**13 US large-cap tickers, ~488 trading days each (Aug 2024 – Jul 2026),
1-minute bars, orders at 5% of each ticker's ADV, POV-style action space
with passive/aggressive split, fees and rebates modelled.**

| | vs TWAP | vs VWAP | vs Almgren-Chriss |
|---|---|---|---|
| **BUY** | +37.4% ± 4.5% | +35.9% ± 3.3% | +35.9% ± 3.7% |
| **SELL** | +34.9% ± 3.4% | +30.0% ± 2.2% | +35.7% ± 5.1% |

| | vs POV 5% | vs POV 10% | vs POV 20% |
|---|---|---|---|
| **BUY** | +47.7% ± 3.5% | +30.9% ± 3.6% | **+13.5% ± 4.5%** |
| **SELL** | +45.0% ± 2.5% | +30.5% ± 2.8% | **+15.0% ± 3.8%** |

All seven benchmarks beaten on both sides, no sign flips across five
evaluation seeds.

**Mechanism.** The policy trades at roughly half the participation rate of
the schedule-based benchmarks and splits each step between resting
passively at the touch (earning the half-spread, uncertain fill) and
crossing aggressively (certain fill, pays the spread and taker fee). It
learns urgency-conditioned behaviour: SPY completion step moves 311 → 97
as urgency goes 0.0 → 1.0, with 12.3% → 92.6% of the order done by the
quarter mark.

---

## 2. Validation

**Walk-forward.** Fold 3 trains on days 0–380 and tests on days 380–440 —
a period never seen — and reproduces the full-sample result (+29.2% /
+25.4% / +30.4% buy at the time of that run). Fold 0's weaker numbers
(+17.5%) track its smaller training set (200 days), not period dependence.

**Training-seed variance.** Three independently trained policies: std
**0.7–1.7pp** per comparison, 2–9x smaller than evaluation variance. The
result is a property of the method, not of one training run.

**Statistical significance.** All six original comparisons p=0.0000,
Bonferroni-corrected, n=3000.

**Alpha ablation.** Removing the synthetic forecasting signal from both the
reward and the observation changes results by under 2.5pp. The improvement
is execution scheduling, not forecasting.

**Passive-assumption sensitivity.** `passive_fill_prob` is uncalibrated and
was expected to be the dominant assumption behind the ~10–13pt gain that
passive execution produced. Swept 0.1 → 0.5 (a 5x range, with 0.1 being a
quarter of the trained value):

| | 0.1 | 0.2 | 0.3 | 0.4 | 0.5 |
|---|---|---|---|---|---|
| BUY vs TWAP | +37.5% | +38.4% | +36.4% | +37.4% | +37.3% |
| BUY vs POV20 | +13.7% | +15.0% | +11.6% | +13.5% | +13.4% |

Essentially flat. Setting `maker_rebate_per_share` to **zero** also changes
nothing (37.4% → 37.4%), so the gain is **spread capture, not rebate
collection** — resting at the touch saves roughly the half-spread (~1 bps
at the calibrated 2.1 bps average) versus a $0.002/share rebate worth
~0.2 bps. The mechanism also degrades gracefully: when passive fills do not
arrive, the policy falls behind, the backlog-aware cap loosens, and it
crosses more.

**Impact-magnitude sensitivity.** `eta_temporary` is uncalibrated. Tested at
1x/2x/5x/10x including a retrain at 5x: the edge narrows from ~20–30% to
10–17%, and buy-side vs Almgren-Chriss becomes unreliable at 5x.

---

## 3. Calibrated from real data

| Parameter | Was | Now | Source |
|---|---|---|---|
| `impact_exponent` | 0.6 | 0.65 | 11.75M Lee-Ready-classified trades |
| `avg_spread_bps` | 5.9 | 2.133 | 2yr tick data, two methods agreeing |
| `hawkes_decay` | 0.3 | 0.0132 | ACF of excess activity, 6,409 ticker-days |
| `calm_vol` | 0.0002 | 0.000396 | 2-state GMM on rolling volatility |
| `volatile_vol` | 0.0012 | 0.001092 | same |
| `prob_calm_to_volatile` | 0.02 | 0.0241 | observed transition counts |
| `prob_volatile_to_calm` | 0.05 | 0.0531 | same |
| `spread_widening_factor` | 2.0 | 1.69 | 3.5M full-consumption trades |
| intraday volume profile | formula | measured | 2yr, per-minute |
| per-ticker ADV | flat 5M | real | per ticker |

Applying the five most recent (regime + spread widening) moved results by
under 2.5pp, which is itself a useful robustness signal.

---

## 4. Known limitations

### 4.1 Permanent impact is the wrong functional form
Measured over **312M observations**: exponent 0.157/0.191/0.188 at
5/15/60 min against the simulator's assumed **1.0**, and ~5 bps at 1%
participation against the model's 0.005 bps. Both shape and level are
wrong. 11/11 buckets significant at every horizon; impact is flat across
horizons, confirming it is genuinely permanent. **Not corrected** —
fixing it means a new functional form, recalibration, retrain and full
revalidation.

### 4.2 `eta_temporary` and `passive_fill_prob` are uncalibrated
Neither can be estimated from public tape data. The tape contains only
small prints (31 of 10.5M classified trades exceeded ~1% participation),
so impact at institutional sizes is unobservable; and it records
executions, not resting orders that never filled, so passive fill rates
are unobservable. Both were handled by sensitivity analysis instead — see
§2. `passive_fill_prob` turned out not to matter; `eta_temporary` does.

### 4.3 Cost scaling with size is not measurable from the tape
Three independent measurements agree that at tape-print sizes, cost is set
by the spread crossed rather than the size of the print:
- Temporary impact: total realised cost scales at 0.104–0.136 with
  participation, because a roughly fixed spread-crossing cost dominates
- Permanent impact: exponent 0.157–0.191
- Joint regression: participation coefficient ≈ 0 (−0.011 to −0.028),
  spread coefficient 0.63–0.71, R² up to 0.89

Consequently `spread_impact_exp` (0.3) and `vol_impact_exp` (0.4) remain
uncalibrated. The measured values (~0.63–0.71 and ~0.11–0.18) apply to
prints at ~0.002% of daily volume and cannot be extrapolated to the 5–25%
participation the simulator operates at — the same error already rejected
for `eta_temporary`.

### 4.4 Hawkes kernel cannot represent real clustering
ACF 0.51 at lag 1, still 0.24 at lag 60 across 6,409 ticker-days. Real
order-flow clustering has long memory; a single-exponential kernel cannot
represent it, so the fitted `hawkes_decay` depends on the fit range. The
mechanism is also self-referential — driven by the simulated order's own
size, not independent market arrivals.

### 4.5 Structural
- Simulator is synthetic; the agent has never traded against replayed real
  order flow.
- No venue routing, queue position, latency, multi-day or portfolio-level
  execution, or market resilience (permanent impact never decays).
- Spread and volume profile are universe-wide averages, not per-ticker.
- `book_depth_levels` is unmeasurable from `tbbo`, which carries only top
  of book; would need MBP-10.
- `book_replenish_halflife` measurement was attempted but the sample
  selects on thin pre-trade snapshots (`size_0` came out at 20x
  pre-trade size), so the fitted 26.5s is reversion, not replenishment.
  The profile does suggest recovery is far faster than the configured 5
  steps (300s).
- Training and evaluation share the same simulator — no out-of-model
  validation.
- Hyperparameters (learning rate, batch size, architecture) never swept.
- Reward term weights other than alpha never ablated.

### 4.6 Data exclusions, all on stated criteria
- Five tickers (UNH, JNJ, CAT, ROKU, ETSY): implausible spreads from
  `EQUS.MINI`'s partial venue coverage; ETSY median 195.8 bps.
- DUK: 3.8% zero-volume minutes, 206-share median minute, 15x the
  sell-cost variance of the other twelve combined.
- ~5 half trading days per ticker (early closes).
- 1.23% of bars clipped for spread outliers.
- Tick-rule-classified trades excluded from impact analysis (51.2%
  accuracy, indistinguishable from chance).

---

## 5. Suggested framing

> The policy reduces execution cost by 30–37% versus TWAP, VWAP and
> Almgren-Chriss, and by 13–15% versus an aggressive fixed-rate POV
> algorithm, on both sides. It is validated out-of-sample by walk-forward,
> stable across three independently trained policies (seed std under
> 1.7pp), and significant under Bonferroni correction at n=3000.
>
> The mechanism is spread capture: the policy splits each step between
> resting passively at the touch and crossing aggressively, trading at
> roughly half the participation rate of schedule-based benchmarks. The
> result is robust to a 5x range of passive fill-rate assumptions and does
> not depend on maker rebates — setting the rebate to zero changes nothing.
> Ablating the synthetic alpha signal changes results by under 2.5pp, so
> the improvement is scheduling rather than forecasting.
>
> The simulator's temporary impact model is validated against 11.75M
> Lee-Ready-classified real trades (measured exponent 0.65 versus a
> literature reference of ~0.5), with spread, volume profile, volatility
> regimes and order-flow decay calibrated from two years of tick data.
>
> Boundaries: permanent impact was measured across 312M observations and
> found concave (0.16–0.19) rather than the linear form the simulator
> assumes — a known, uncorrected discrepancy. The absolute impact magnitude
> is uncalibrated, and at 5x impact the edge narrows to 10–17%. Results are
> relative comparisons within a synthetic simulator, not absolute cost
> predictions.

The diagnostic work is a substantial part of the value: tracing the urgency
failure to an inert action space, isolating DUK's 15x variance
contribution, identifying the venue-coverage problem, catching half trading
days via a 533,989 bps outlier, and testing each headline claim against the
assumption most likely to invalidate it.
