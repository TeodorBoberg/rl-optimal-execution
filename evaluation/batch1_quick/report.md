# Batch 1 report

Folds [3]; 20 paired episodes per fold and side; 1 trained policies. Every strategy in an episode trades the same ticker and day.

## 0. Metric check: clipped vs signed cost

Mean cost in bps, averaged over all folds and both sides. The clipped metric charges adverse drift and never credits favourable drift; `drift charge` is how much of the old number that asymmetry accounts for.

| strategy | clipped (old) | signed IS | drift charge | finish step | done by 25% |
|---|---|---|---|---|---|
| TWAP | 45.7 | 11.9 | 33.8 | 390.0 | 24.9 |
| VWAP | 44.1 | 12.3 | 31.9 | 390.0 | 32.6 |
| AC (preset, 0.6) | 37.0 | 8.8 | 28.2 | 388.2 | 60.7 |
| POV 5% | 51.5 | 21.5 | 30.0 | 381.1 | 28.3 |
| POV 10% | 38.8 | 10.2 | 28.6 | 262.6 | 56.0 |
| POV 20% | 30.7 | 9.6 | 21.1 | 108.0 | 88.7 |
| RL agent | 31.1 | 8.6 | 22.6 | 97.5 | 92.7 |

## 1. Headline: agent vs benchmarks, 1 runs

**Old metric (clipped)**: % cost reduction, mean ± std across runs. This should reproduce the published table.

| vs | buy | sell | buy+sell | runs > 0 |
|---|---|---|---|---|
| TWAP | +35.8 | +28.4 | +31.9 | 1/1 |
| VWAP | +33.5 | +25.8 | +29.5 | 1/1 |
| AC (preset, 0.6) | +21.6 | +10.6 | +15.9 | 1/1 |
| POV 5% | +40.3 | +38.8 | +39.5 | 1/1 |
| POV 10% | +19.7 | +19.7 | +19.7 | 1/1 |
| POV 20% | +3.0 | -5.6 | -1.6 | 0/1 |

**Signed implementation shortfall**: cost saved in **bps** (benchmark − agent), mean ± std across runs. Percentages are not used because signed means can sit near zero. `buy+sell` averages each run's buy and sell results; buy and sell episodes share days, so market drift cancels exactly and what remains is execution.

| vs | buy | sell | buy+sell | runs > 0 |
|---|---|---|---|---|
| TWAP | +4.3 | +2.5 | +3.4 | 1/1 |
| VWAP | +4.9 | +2.6 | +3.7 | 1/1 |
| AC (preset, 0.6) | +3.4 | -2.9 | +0.3 | 1/1 |
| POV 5% | +11.6 | +14.2 | +12.9 | 1/1 |
| POV 10% | +0.2 | +3.0 | +1.6 | 1/1 |
| POV 20% | +3.4 | -1.3 | +1.0 | 1/1 |

## 2. Benchmark sweep: is the agent better than the best setting?

Mean cost (bps) at every setting, all folds and sides.

| setting | clipped | signed | signed std | finish step |
|---|---|---|---|---|
| TWAP | 45.7 | 11.9 | 99.1 | 390.0 |
| VWAP | 44.1 | 12.3 | 91.7 | 390.0 |
| AC ra=0.01 | 45.4 | 11.8 | 98.3 | 390.0 |
| AC ra=0.05 | 44.2 | 11.3 | 95.5 | 390.0 |
| AC ra=0.2 | 41.0 | 10.0 | 88.1 | 390.0 |
| AC (preset, 0.6) | 37.0 | 8.8 | 77.9 | 388.2 |
| AC ra=1.5 | 33.7 | 8.3 | 68.7 | 376.6 |
| AC ra=20 | 29.3 | 9.1 | 52.6 | 156.8 |
| AC ra=5 | 30.6 | 8.4 | 58.8 | 258.9 |
| POV 10% | 38.8 | 10.2 | 82.0 | 262.6 |
| POV 12.5% | 35.8 | 9.4 | 74.2 | 210.1 |
| POV 15% | 33.6 | 9.2 | 67.6 | 164.2 |
| POV 17.5% | 32.0 | 9.4 | 61.9 | 131.6 |
| POV 20% | 30.7 | 9.6 | 57.3 | 108.0 |
| POV 22.5% | 30.1 | 10.0 | 54.4 | 90.8 |
| POV 25% | 29.6 | 10.3 | 52.1 | 79.3 |
| POV 5% | 51.5 | 21.5 | 96.7 | 381.1 |
| POV 7.5% | 42.9 | 12.9 | 91.0 | 318.9 |
| RL agent | 31.1 | 8.6 | 62.8 | 97.5 |

**Agent vs the best setting of each family.** The best setting for fold *k* is chosen on the other folds (leave-one-fold-out), so it is not fitted to the episodes it is scored on. `oracle` picks on all folds including the scored one and is the most generous possible benchmark.

| comparison | oracle pick | LOFO picks | saving vs LOFO (bps) | saving vs oracle (bps) | runs > 0 (LOFO) |
|---|---|---|---|---|---|
| clipped (old): best AC | AC ra=20 | AC ra=20 | -1.88 ± 0.00 | -1.88 ± 0.00 | 0/1 |
| clipped (old): best POV | POV 25% | POV 25% | -1.49 ± 0.00 | -1.49 ± 0.00 | 0/1 |
| signed IS: best AC | AC ra=1.5 | AC ra=1.5 | -0.29 ± 0.00 | -0.29 ± 0.00 | 0/1 |
| signed IS: best POV | POV 15% | POV 15% | +0.67 ± 0.00 | +0.67 ± 0.00 | 1/1 |

## 3. Cost-vs-risk frontier

Signed IS. x = standard deviation of per-episode cost (risk, computed within side and averaged), y = mean cost. Down and left is better. The AC curve is the classical efficient frontier traced by risk aversion; the POV curve by participation rate. See `frontier.png`.

RL agent (pooled over all runs): mean 8.6 bps, risk 62.8 bps. Single runs are each scored on one fold's test period, so they scatter with the period as well as the policy.

- Settings that are both cheaper AND less risky than the agent: AC ra=5
- Settings the agent beats on both: AC ra=0.01, AC ra=0.05, AC ra=0.2, AC (preset, 0.6), POV 10%, POV 12.5%, POV 15%, POV 5%, POV 7.5%, TWAP, VWAP

## 4. Where the cost comes from (signed IS decomposition)

bps, mean over all episodes. Buy and sell are averaged, so the drift column is ~0 by construction; its per-side size is shown separately.

| strategy | drift | own permanent | execution | fees | total | |drift| per side | drift std |
|---|---|---|---|---|---|---|---|
| TWAP | -0.00 | 8.69 | 2.86 | 0.40 | 11.94 | 5.35 | 99.05 |
| VWAP | -0.00 | 8.51 | 3.38 | 0.40 | 12.28 | 5.10 | 91.71 |
| AC (preset, 0.6) | -0.00 | 4.78 | 3.65 | 0.40 | 8.83 | 3.09 | 77.92 |
| POV 5% | -0.00 | 8.97 | 12.10 | 0.40 | 21.47 | 7.53 | 95.97 |
| POV 10% | -0.00 | 5.33 | 4.44 | 0.40 | 10.17 | 7.68 | 82.00 |
| POV 20% | 0.00 | 2.44 | 6.75 | 0.40 | 9.60 | 3.91 | 57.27 |
| RL agent | 0.54 | 2.09 | 5.58 | 0.36 | 8.57 | 6.00 | 62.90 |

## 5. Significance: day-clustered bootstrap

Paired difference benchmark − agent (bps), pooled over all runs. Episodes on the same ticker and day are correlated (same price path), so the bootstrap resamples whole ticker-days. CI is 99.38% (Bonferroni over 8 comparisons). The naive t-test treats every episode as independent and is shown for contrast.

| comparison | mean diff | CI | excludes 0 | ticker-days | naive p |
|---|---|---|---|---|---|
| clipped (old): TWAP | +14.62 | [+6.87, +24.55] | yes | 20 | 2.7e-03 |
| clipped (old): VWAP | +13.01 | [+6.76, +20.55] | yes | 20 | 1.8e-03 |
| clipped (old): AC (preset, 0.6) | +5.88 | [+2.24, +10.93] | yes | 20 | 9.4e-03 |
| clipped (old): POV 5% | +20.33 | [+12.86, +28.00] | yes | 20 | 1.5e-04 |
| clipped (old): POV 10% | +7.65 | [+2.70, +13.63] | yes | 20 | 1.2e-02 |
| clipped (old): POV 20% | -0.48 | [-2.73, +1.65] | NO | 20 | 7.3e-01 |
| clipped (old): AC ra=20 (best) | -1.88 | [-4.78, +0.54] | NO | 20 | 2.2e-01 |
| clipped (old): POV 25% (best) | -1.49 | [-5.50, +1.73] | NO | 20 | 4.6e-01 |
| signed IS: TWAP | +3.37 | [+1.54, +5.16] | yes | 20 | 6.3e-01 |
| signed IS: VWAP | +3.71 | [+1.87, +5.53] | yes | 20 | 5.4e-01 |
| signed IS: AC (preset, 0.6) | +0.25 | [-1.66, +2.12] | NO | 20 | 9.4e-01 |
| signed IS: POV 5% | +12.90 | [+6.31, +20.04] | yes | 20 | 8.0e-02 |
| signed IS: POV 10% | +1.60 | [-0.47, +3.74] | NO | 20 | 7.2e-01 |
| signed IS: POV 20% | +1.03 | [-1.30, +3.92] | NO | 20 | 6.5e-01 |
| signed IS: AC ra=1.5 (best) | -0.29 | [-1.99, +1.72] | NO | 20 | 8.8e-01 |
| signed IS: POV 15% (best) | +0.67 | [-1.44, +2.78] | NO | 20 | 7.7e-01 |

## 6. What the agent does

From per-step traces. Participation = shares filled / bar volume, only over steps where the order was still open. See `behaviour.png`.

| agent participation % by quintile of | Q1 | Q2 | Q3 | Q4 | Q5 |
|---|---|---|---|---|---|
| prev-bar volume | 24.1 | 24.7 | 23.9 | 22.2 | 7.8 |
| prev-bar spread | 24.0 | 20.9 | 20.9 | 19.0 | 17.7 |
| price vs arrival | 20.7 | 23.6 | 20.9 | 19.3 | 18.2 |
| alpha signal |  |  |  |  |  |

Agent participation: calm regime 19.5%, volatile regime 23.2%. Mean passive fraction of its orders: 22.4%.

Step-by-step correlation of agent and POV 20% participation (same episodes): 0.80.

## 7. Urgency conditioning (causal models)

| urgency | % done by 25% | % done by 50% | finish step | signed IS | clipped |
|---|---|---|---|---|---|
| 0.0 | 28.2 | 68.6 | 267.8 | 7.3 | 37.5 |
| 0.25 | 68.2 | 98.6 | 155.5 | 12.0 | 43.1 |
| 0.5 | 94.7 | 100.0 | 101.2 | 8.7 | 41.6 |
| 0.75 | 96.6 | 100.0 | 93.1 | 9.3 | 39.7 |
| 1.0 | 96.6 | 100.0 | 92.1 | 8.6 | 38.0 |

Policies whose completion rises monotonically with urgency (Spearman ρ = 1): 0/1; median ρ 0.97.
