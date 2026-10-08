# Batch 1 report

Run configuration: `overrides: market.permanent_impact_mode=cumulative, reward_weights.disable_alpha_signal=true`

Folds [3]; 1000 paired episodes per fold and side; 3 trained policies. Every strategy in an episode trades the same ticker and day.

## 0. Metric check: clipped vs signed cost

Mean cost in bps, averaged over all folds and both sides. The clipped metric charges adverse drift and never credits favourable drift; `drift charge` is how much of the old number that asymmetry accounts for.

| strategy | clipped (old) | signed IS | drift charge | finish step | done by 25% |
|---|---|---|---|---|---|
| TWAP | 55.3 | 8.3 | 47.0 | 390.0 | 24.8 |
| VWAP | 54.3 | 8.8 | 45.5 | 390.0 | 32.4 |
| AC (preset, 0.6) | 47.9 | 9.0 | 38.9 | 388.2 | 59.8 |
| POV 5% | 66.2 | 22.6 | 43.6 | 372.0 | 27.6 |
| POV 10% | 50.3 | 10.8 | 39.5 | 261.9 | 53.9 |
| POV 20% | 43.6 | 11.8 | 31.8 | 113.7 | 87.0 |
| RL agent | 49.9 | 5.7 | 44.2 | 320.4 | 42.6 |

## 1. Headline: agent vs benchmarks, 3 runs

**Old metric (clipped)**: % cost reduction, mean ± std across runs. This should reproduce the published table.

| vs | buy | sell | buy+sell | runs > 0 |
|---|---|---|---|---|
| TWAP | +8.3 ± 0.3 | +11.2 ± 1.1 | +9.7 ± 0.7 | 3/3 |
| VWAP | +6.8 ± 0.3 | +9.5 ± 1.2 | +8.1 ± 0.7 | 3/3 |
| AC (preset, 0.6) | -5.2 ± 0.4 | -3.4 ± 1.3 | -4.3 ± 0.8 | 0/3 |
| POV 5% | +24.5 ± 0.3 | +24.7 ± 1.0 | +24.6 ± 0.6 | 3/3 |
| POV 10% | +0.6 ± 0.3 | +0.8 ± 1.3 | +0.7 ± 0.7 | 3/3 |
| POV 20% | -16.0 ± 0.4 | -13.0 ± 1.4 | -14.5 ± 0.9 | 0/3 |

**Signed implementation shortfall**: cost saved in **bps** (benchmark − agent), mean ± std across runs. Percentages are not used because signed means can sit near zero. `buy+sell` averages each run's buy and sell results; buy and sell episodes share days, so market drift cancels exactly and what remains is execution.

| vs | buy | sell | buy+sell | runs > 0 |
|---|---|---|---|---|
| TWAP | +1.4 ± 0.1 | +3.7 ± 0.2 | +2.5 ± 0.1 | 3/3 |
| VWAP | +1.9 ± 0.1 | +4.3 ± 0.2 | +3.1 ± 0.1 | 3/3 |
| AC (preset, 0.6) | +2.0 ± 0.1 | +4.5 ± 0.2 | +3.3 ± 0.1 | 3/3 |
| POV 5% | +17.1 ± 0.1 | +16.6 ± 0.2 | +16.9 ± 0.1 | 3/3 |
| POV 10% | +4.7 ± 0.1 | +5.5 ± 0.2 | +5.1 ± 0.1 | 3/3 |
| POV 20% | +3.9 ± 0.1 | +8.3 ± 0.2 | +6.1 ± 0.1 | 3/3 |

## 2. Benchmark sweep: is the agent better than the best setting?

Mean cost (bps) at every setting, all folds and sides.

| setting | clipped | signed | signed std | finish step |
|---|---|---|---|---|
| TWAP | 55.3 | 8.3 | 126.4 | 390.0 |
| VWAP | 54.3 | 8.8 | 121.4 | 390.0 |
| AC ra=0.01 | 55.0 | 8.3 | 125.5 | 390.0 |
| AC ra=0.05 | 53.8 | 8.3 | 122.3 | 390.0 |
| AC ra=0.2 | 51.1 | 8.5 | 114.7 | 390.0 |
| AC (preset, 0.6) | 47.9 | 9.0 | 106.2 | 388.2 |
| AC ra=1.5 | 45.4 | 9.6 | 100.0 | 377.1 |
| AC ra=20 | 42.3 | 11.6 | 90.8 | 162.5 |
| AC ra=5 | 43.3 | 10.6 | 94.2 | 263.5 |
| POV 10% | 50.3 | 10.8 | 109.5 | 261.9 |
| POV 12.5% | 47.6 | 10.4 | 104.3 | 209.2 |
| POV 15% | 45.9 | 10.8 | 100.0 | 166.7 |
| POV 17.5% | 44.5 | 11.3 | 96.4 | 136.2 |
| POV 20% | 43.6 | 11.8 | 93.6 | 113.7 |
| POV 22.5% | 42.9 | 12.4 | 91.4 | 97.1 |
| POV 25% | 42.3 | 12.9 | 89.5 | 84.4 |
| POV 5% | 66.2 | 22.6 | 129.0 | 372.0 |
| POV 7.5% | 55.6 | 13.5 | 117.6 | 321.6 |
| RL agent | 49.9 | 5.7 | 115.0 | 320.4 |

**Agent vs the best setting of each family.** The best setting for fold *k* is chosen on the other folds (leave-one-fold-out), so it is not fitted to the episodes it is scored on. `oracle` picks on all folds including the scored one and is the most generous possible benchmark.

| comparison | oracle pick | LOFO picks | saving vs LOFO (bps) | saving vs oracle (bps) | runs > 0 (LOFO) |
|---|---|---|---|---|---|
| clipped (old): best AC | AC ra=20 | AC ra=20 | -7.67 ± 0.38 | -7.67 ± 0.38 | 0/3 |
| clipped (old): best POV | POV 25% | POV 25% | -7.67 ± 0.38 | -7.67 ± 0.38 | 0/3 |
| signed IS: best AC | AC ra=0.01 | AC ra=0.01 | +2.53 ± 0.06 | +2.53 ± 0.06 | 3/3 |
| signed IS: best POV | POV 12.5% | POV 12.5% | +4.67 ± 0.06 | +4.67 ± 0.06 | 3/3 |

## 3. Cost-vs-risk frontier

Signed IS. x = standard deviation of per-episode cost (risk, computed within side and averaged), y = mean cost. Down and left is better. The AC curve is the classical efficient frontier traced by risk aversion; the POV curve by participation rate. See `frontier.png`.

RL agent (pooled over all runs): mean 5.7 bps, risk 115.0 bps. Single runs are each scored on one fold's test period, so they scatter with the period as well as the policy.

- Settings that are both cheaper AND less risky than the agent: none
- Settings the agent beats on both: AC ra=0.01, AC ra=0.05, POV 5%, POV 7.5%, TWAP, VWAP

## 4. Where the cost comes from (signed IS decomposition)

bps, mean over all episodes. Buy and sell are averaged, so the drift column is ~0 by construction; its per-side size is shown separately.

| strategy | drift | own permanent | execution | fees | total | |drift| per side | drift std |
|---|---|---|---|---|---|---|---|
| TWAP | 0.00 | 5.00 | 2.85 | 0.41 | 8.26 | 4.46 | 126.38 |
| VWAP | 0.00 | 5.00 | 3.42 | 0.41 | 8.83 | 4.37 | 121.36 |
| AC (preset, 0.6) | -0.00 | 5.00 | 3.58 | 0.41 | 8.99 | 4.32 | 106.24 |
| POV 5% | 0.00 | 5.00 | 17.17 | 0.41 | 22.59 | 5.81 | 126.53 |
| POV 10% | 0.00 | 5.00 | 5.42 | 0.41 | 10.83 | 5.15 | 109.31 |
| POV 20% | 0.00 | 5.00 | 6.42 | 0.41 | 11.84 | 3.39 | 93.59 |
| RL agent | 0.01 | 5.00 | 0.63 | 0.09 | 5.74 | 5.61 | 114.98 |

## 5. Significance: day-clustered bootstrap

Paired difference benchmark − agent (bps), pooled over all runs. Episodes on the same ticker and day are correlated (same price path), so the bootstrap resamples whole ticker-days. CI is 99.38% (Bonferroni over 8 comparisons). The naive t-test treats every episode as independent and is shown for contrast.

| comparison | mean diff | CI | excludes 0 | ticker-days | naive p |
|---|---|---|---|---|---|
| clipped (old): TWAP | +5.36 | [+4.21, +6.59] | yes | 568 | 3.0e-117 |
| clipped (old): VWAP | +4.40 | [+3.32, +5.53] | yes | 568 | 4.1e-94 |
| clipped (old): AC (preset, 0.6) | -2.07 | [-3.11, -1.11] | yes | 568 | 2.7e-29 |
| clipped (old): POV 5% | +16.30 | [+13.82, +18.98] | yes | 568 | 0.0e+00 |
| clipped (old): POV 10% | +0.35 | [-0.56, +1.25] | NO | 568 | 2.7e-02 |
| clipped (old): POV 20% | -6.33 | [-8.57, -4.37] | yes | 568 | 2.8e-70 |
| clipped (old): AC ra=20 (best) | -7.67 | [-9.84, -5.60] | yes | 568 | 3.2e-86 |
| clipped (old): POV 25% (best) | -7.67 | [-10.02, -5.47] | yes | 568 | 6.3e-75 |
| signed IS: TWAP | +2.53 | [+2.32, +2.71] | yes | 568 | 3.5e-13 |
| signed IS: VWAP | +3.09 | [+2.89, +3.31] | yes | 568 | 2.3e-22 |
| signed IS: AC (preset, 0.6) | +3.26 | [+3.00, +3.49] | yes | 568 | 1.7e-29 |
| signed IS: POV 5% | +16.85 | [+14.14, +20.12] | yes | 568 | 5.6e-232 |
| signed IS: POV 10% | +5.09 | [+4.58, +5.68] | yes | 568 | 1.0e-103 |
| signed IS: POV 20% | +6.10 | [+5.59, +6.63] | yes | 568 | 1.3e-26 |
| signed IS: AC ra=0.01 (best) | +2.53 | [+2.30, +2.72] | yes | 568 | 3.4e-14 |
| signed IS: POV 12.5% (best) | +4.67 | [+4.31, +5.09] | yes | 568 | 8.4e-46 |

## 6. What the agent does

From per-step traces. Participation = shares filled / bar volume, only over steps where the order was still open. See `behaviour.png`.

| agent participation % by quintile of | Q1 | Q2 | Q3 | Q4 | Q5 |
|---|---|---|---|---|---|
| prev-bar volume | 13.8 | 11.0 | 8.8 | 7.7 | 6.9 |
| prev-bar spread | 10.7 | 11.2 | 9.3 | 9.0 | 8.0 |
| price vs arrival | 9.2 | 10.3 | 10.7 | 9.3 | 8.7 |
| alpha signal |  |  |  |  |  |

Agent participation: calm regime 9.6%, volatile regime 9.6%. Mean passive fraction of its orders: 88.2%.

Step-by-step correlation of agent and POV 20% participation (same episodes): 0.26.
