# Batch 1 report

Folds [0, 1, 2, 3]; 1000 paired episodes per fold and side; 12 trained policies. Every strategy in an episode trades the same ticker and day.

## 0. Metric check: clipped vs signed cost

Mean cost in bps, averaged over all folds and both sides. The clipped metric charges adverse drift and never credits favourable drift; `drift charge` is how much of the old number that asymmetry accounts for.

| strategy | clipped (old) | signed IS | drift charge | finish step | done by 25% |
|---|---|---|---|---|---|
| TWAP | 52.8 | 11.9 | 40.9 | 390.0 | 24.7 |
| VWAP | 51.8 | 12.3 | 39.5 | 390.0 | 32.3 |
| AC (preset, 0.6) | 44.1 | 8.7 | 35.4 | 388.3 | 59.5 |
| POV 5% | 62.7 | 24.9 | 37.8 | 368.9 | 28.2 |
| POV 10% | 46.3 | 11.2 | 35.2 | 259.0 | 54.0 |
| POV 20% | 38.5 | 9.0 | 29.5 | 116.3 | 86.4 |
| RL agent | 39.2 | 8.0 | 31.2 | 104.4 | 91.2 |

## 1. Headline: agent vs benchmarks, 12 runs

**Old metric (clipped)**: % cost reduction, mean ± std across runs. This should reproduce the published table.

| vs | buy | sell | buy+sell | runs > 0 |
|---|---|---|---|---|
| TWAP | +27.2 ± 2.4 | +24.8 ± 2.8 | +26.0 ± 2.4 | 12/12 |
| VWAP | +25.6 ± 2.2 | +23.4 ± 2.9 | +24.5 ± 2.4 | 12/12 |
| AC (preset, 0.6) | +12.1 ± 2.2 | +10.5 ± 2.3 | +11.3 ± 2.2 | 12/12 |
| POV 5% | +38.0 ± 4.2 | +36.1 ± 3.9 | +37.1 ± 3.9 | 12/12 |
| POV 10% | +15.9 ± 2.3 | +14.5 ± 3.3 | +15.2 ± 2.7 | 12/12 |
| POV 20% | -2.0 ± 2.9 | -1.9 ± 3.1 | -2.0 ± 2.9 | 4/12 |

**Signed implementation shortfall**: cost saved in **bps** (benchmark − agent), mean ± std across runs. Percentages are not used because signed means can sit near zero. `buy+sell` averages each run's buy and sell results; buy and sell episodes share days, so market drift cancels exactly and what remains is execution.

| vs | buy | sell | buy+sell | runs > 0 |
|---|---|---|---|---|
| TWAP | +5.4 ± 1.0 | +2.6 ± 0.7 | +4.0 ± 0.6 | 12/12 |
| VWAP | +5.5 ± 1.0 | +3.1 ± 0.8 | +4.3 ± 0.5 | 12/12 |
| AC (preset, 0.6) | +1.4 ± 1.1 | +0.0 ± 0.9 | +0.7 ± 0.5 | 12/12 |
| POV 5% | +17.9 ± 4.0 | +16.0 ± 5.4 | +16.9 ± 4.3 | 12/12 |
| POV 10% | +3.7 ± 1.2 | +2.6 ± 1.9 | +3.2 ± 0.6 | 12/12 |
| POV 20% | +1.1 ± 0.6 | +1.0 ± 0.7 | +1.0 ± 0.4 | 12/12 |

## 2. Benchmark sweep: is the agent better than the best setting?

Mean cost (bps) at every setting, all folds and sides.

| setting | clipped | signed | signed std | finish step |
|---|---|---|---|---|
| TWAP | 52.8 | 11.9 | 125.2 | 390.0 |
| VWAP | 51.8 | 12.3 | 120.7 | 390.0 |
| AC ra=0.01 | 52.5 | 11.8 | 124.4 | 390.0 |
| AC ra=0.05 | 51.1 | 11.2 | 121.5 | 390.0 |
| AC ra=0.2 | 47.9 | 9.9 | 114.7 | 390.0 |
| AC (preset, 0.6) | 44.1 | 8.7 | 107.1 | 388.3 |
| AC ra=1.5 | 41.2 | 8.1 | 101.3 | 377.5 |
| AC ra=20 | 37.2 | 8.4 | 92.8 | 164.6 |
| AC ra=5 | 38.6 | 8.0 | 96.1 | 265.5 |
| POV 10% | 46.3 | 11.2 | 108.4 | 259.0 |
| POV 12.5% | 43.2 | 9.6 | 103.9 | 208.3 |
| POV 15% | 41.2 | 9.1 | 100.4 | 168.2 |
| POV 17.5% | 39.7 | 9.0 | 97.5 | 138.6 |
| POV 20% | 38.5 | 9.0 | 95.1 | 116.3 |
| POV 22.5% | 37.6 | 9.2 | 93.1 | 99.6 |
| POV 25% | 36.9 | 9.4 | 91.4 | 86.6 |
| POV 5% | 62.7 | 24.9 | 127.3 | 368.9 |
| POV 7.5% | 52.0 | 15.1 | 115.6 | 318.1 |
| RL agent | 39.2 | 8.0 | 97.8 | 104.4 |

**Agent vs the best setting of each family.** The best setting for fold *k* is chosen on the other folds (leave-one-fold-out), so it is not fitted to the episodes it is scored on. `oracle` picks on all folds including the scored one and is the most generous possible benchmark.

| comparison | oracle pick | LOFO picks | saving vs LOFO (bps) | saving vs oracle (bps) | runs > 0 (LOFO) |
|---|---|---|---|---|---|
| clipped (old): best AC | AC ra=20 | AC ra=20 | -2.00 ± 0.80 | -2.00 ± 0.80 | 0/12 |
| clipped (old): best POV | POV 25% | POV 25% | -2.31 ± 0.92 | -2.31 ± 0.92 | 0/12 |
| signed IS: best AC | AC ra=5 | AC ra=5 | -0.01 ± 0.41 | -0.01 ± 0.41 | 3/12 |
| signed IS: best POV | POV 17.5% | POV 17.5% | +0.99 ± 0.42 | +0.99 ± 0.42 | 12/12 |

## 3. Cost-vs-risk frontier

Signed IS. x = standard deviation of per-episode cost (risk, computed within side and averaged), y = mean cost. Down and left is better. The AC curve is the classical efficient frontier traced by risk aversion; the POV curve by participation rate. See `frontier.png`.

RL agent (pooled over all runs): mean 8.0 bps, risk 98.8 bps. Single runs are each scored on one fold's test period, so they scatter with the period as well as the policy.

- Settings that are both cheaper AND less risky than the agent: AC ra=5
- Settings the agent beats on both: AC ra=0.01, AC ra=0.05, AC ra=0.2, AC (preset, 0.6), AC ra=1.5, POV 10%, POV 12.5%, POV 15%, POV 5%, POV 7.5%, TWAP, VWAP

## 4. Where the cost comes from (signed IS decomposition)

bps, mean over all episodes. Buy and sell are averaged, so the drift column is ~0 by construction; its per-side size is shown separately.

| strategy | drift | own permanent | execution | fees | total | |drift| per side | drift std |
|---|---|---|---|---|---|---|---|
| TWAP | 0.00 | 8.73 | 2.78 | 0.43 | 11.94 | 0.53 | 125.22 |
| VWAP | 0.00 | 8.55 | 3.28 | 0.43 | 12.26 | 0.30 | 120.73 |
| AC (preset, 0.6) | 0.00 | 4.88 | 3.39 | 0.43 | 8.70 | 0.18 | 107.07 |
| POV 5% | -0.00 | 8.86 | 15.63 | 0.43 | 24.92 | 0.05 | 124.50 |
| POV 10% | 0.00 | 5.39 | 5.35 | 0.43 | 11.16 | 0.31 | 108.05 |
| POV 20% | -0.00 | 2.63 | 5.97 | 0.43 | 9.03 | 0.83 | 95.05 |
| RL agent | -0.02 | 2.28 | 5.33 | 0.40 | 7.98 | 0.82 | 98.74 |

## 5. Significance: day-clustered bootstrap

Paired difference benchmark − agent (bps), pooled over all runs. Episodes on the same ticker and day are correlated (same price path), so the bootstrap resamples whole ticker-days. CI is 99.38% (Bonferroni over 8 comparisons). The naive t-test treats every episode as independent and is shown for contrast.

| comparison | mean diff | CI | excludes 0 | ticker-days | naive p |
|---|---|---|---|---|---|
| clipped (old): TWAP | +13.66 | [+12.38, +15.09] | yes | 2272 | 0.0e+00 |
| clipped (old): VWAP | +12.59 | [+11.35, +13.91] | yes | 2272 | 0.0e+00 |
| clipped (old): AC (preset, 0.6) | +4.91 | [+4.34, +5.56] | yes | 2272 | 0.0e+00 |
| clipped (old): POV 5% | +23.57 | [+21.64, +25.43] | yes | 2272 | 0.0e+00 |
| clipped (old): POV 10% | +7.17 | [+6.32, +8.12] | yes | 2272 | 0.0e+00 |
| clipped (old): POV 20% | -0.65 | [-1.13, -0.16] | yes | 2272 | 2.6e-15 |
| clipped (old): AC ra=20 (best) | -2.00 | [-2.38, -1.66] | yes | 2272 | 7.5e-194 |
| clipped (old): POV 25% (best) | -2.31 | [-2.81, -1.82] | yes | 2272 | 4.5e-132 |
| signed IS: TWAP | +3.96 | [+3.83, +4.11] | yes | 2272 | 8.4e-27 |
| signed IS: VWAP | +4.28 | [+4.15, +4.40] | yes | 2272 | 9.0e-37 |
| signed IS: AC (preset, 0.6) | +0.72 | [+0.61, +0.83] | yes | 2272 | 2.8e-05 |
| signed IS: POV 5% | +16.94 | [+15.39, +18.65] | yes | 2272 | 0.0e+00 |
| signed IS: POV 10% | +3.18 | [+2.71, +3.72] | yes | 2272 | 2.6e-45 |
| signed IS: POV 20% | +1.05 | [+0.89, +1.20] | yes | 2272 | 1.5e-16 |
| signed IS: AC ra=5 (best) | -0.01 | [-0.12, +0.09] | NO | 2272 | 8.8e-01 |
| signed IS: POV 17.5% (best) | +0.99 | [+0.84, +1.17] | yes | 2272 | 1.2e-14 |

## 6. What the agent does

From per-step traces. Participation = shares filled / bar volume, only over steps where the order was still open. See `behaviour.png`.

| agent participation % by quintile of | Q1 | Q2 | Q3 | Q4 | Q5 |
|---|---|---|---|---|---|
| prev-bar volume | 24.7 | 24.8 | 24.8 | 24.5 | 14.9 |
| prev-bar spread | 23.4 | 23.4 | 22.9 | 22.1 | 21.9 |
| price vs arrival | 22.3 | 23.0 | 22.5 | 23.1 | 22.8 |
| alpha signal |  |  |  |  |  |

Agent participation: calm regime 22.4%, volatile regime 23.7%. Mean passive fraction of its orders: 10.4%.

Step-by-step correlation of agent and POV 20% participation (same episodes): 0.85.

## 7. Urgency conditioning (causal models)

| urgency | % done by 25% | % done by 50% | finish step | signed IS | clipped |
|---|---|---|---|---|---|
| 0.0 | 26.0 | 66.3 | 272.9 | 6.2 | 48.2 |
| 0.25 | 70.8 | 98.2 | 150.4 | 7.1 | 41.2 |
| 0.5 | 90.8 | 99.1 | 105.0 | 8.0 | 37.6 |
| 0.75 | 92.3 | 99.2 | 92.7 | 8.7 | 36.2 |
| 1.0 | 92.6 | 99.2 | 89.3 | 9.0 | 35.6 |

Policies whose completion rises monotonically with urgency (Spearman ρ = 1): 12/12; median ρ 1.00.
