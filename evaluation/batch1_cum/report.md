# Batch 1 report

Run configuration: `overrides: market.permanent_impact_mode=cumulative`

Folds [0, 1, 2, 3]; 1000 paired episodes per fold and side; 12 trained policies. Every strategy in an episode trades the same ticker and day.

## 0. Metric check: clipped vs signed cost

Mean cost in bps, averaged over all folds and both sides. The clipped metric charges adverse drift and never credits favourable drift; `drift charge` is how much of the old number that asymmetry accounts for.

| strategy | clipped (old) | signed IS | drift charge | finish step | done by 25% |
|---|---|---|---|---|---|
| TWAP | 50.8 | 8.2 | 42.6 | 390.0 | 24.7 |
| VWAP | 49.8 | 8.7 | 41.1 | 390.0 | 32.3 |
| AC (preset, 0.6) | 44.1 | 8.8 | 35.3 | 388.3 | 59.5 |
| POV 5% | 60.4 | 21.1 | 39.3 | 368.9 | 28.2 |
| POV 10% | 46.1 | 10.8 | 35.3 | 259.0 | 54.0 |
| POV 20% | 39.8 | 11.4 | 28.4 | 116.3 | 86.4 |
| RL agent | 40.7 | 10.7 | 30.0 | 104.4 | 91.2 |

## 1. Headline: agent vs benchmarks, 12 runs

**Old metric (clipped)**: % cost reduction, mean ± std across runs. This should reproduce the published table.

| vs | buy | sell | buy+sell | runs > 0 |
|---|---|---|---|---|
| TWAP | +21.3 ± 1.8 | +18.8 ± 2.4 | +20.0 ± 1.9 | 12/12 |
| VWAP | +19.6 ± 1.6 | +17.4 ± 2.4 | +18.5 ± 1.8 | 12/12 |
| AC (preset, 0.6) | +8.7 ± 1.9 | +7.2 ± 2.0 | +8.0 ± 1.8 | 12/12 |
| POV 5% | +32.9 ± 5.0 | +31.1 ± 4.8 | +32.0 ± 4.8 | 12/12 |
| POV 10% | +12.1 ± 2.3 | +10.9 ± 3.5 | +11.5 ± 2.8 | 12/12 |
| POV 20% | -2.3 ± 2.7 | -2.2 ± 2.9 | -2.3 ± 2.7 | 3/12 |

**Signed implementation shortfall**: cost saved in **bps** (benchmark − agent), mean ± std across runs. Percentages are not used because signed means can sit near zero. `buy+sell` averages each run's buy and sell results; buy and sell episodes share days, so market drift cancels exactly and what remains is execution.

| vs | buy | sell | buy+sell | runs > 0 |
|---|---|---|---|---|
| TWAP | -1.1 ± 0.9 | -3.9 ± 0.7 | -2.5 ± 0.4 | 0/12 |
| VWAP | -0.8 ± 0.9 | -3.1 ± 0.8 | -2.0 ± 0.4 | 0/12 |
| AC (preset, 0.6) | -1.2 ± 1.0 | -2.6 ± 0.9 | -1.9 ± 0.4 | 0/12 |
| POV 5% | +11.3 ± 3.7 | +9.5 ± 5.2 | +10.4 ± 4.0 | 12/12 |
| POV 10% | +0.6 ± 1.4 | -0.5 ± 1.8 | +0.1 ± 0.6 | 6/12 |
| POV 20% | +0.7 ± 0.7 | +0.7 ± 0.7 | +0.7 ± 0.5 | 11/12 |

## 2. Benchmark sweep: is the agent better than the best setting?

Mean cost (bps) at every setting, all folds and sides.

| setting | clipped | signed | signed std | finish step |
|---|---|---|---|---|
| TWAP | 50.8 | 8.2 | 125.2 | 390.0 |
| VWAP | 49.8 | 8.7 | 120.7 | 390.0 |
| AC ra=0.01 | 50.5 | 8.2 | 124.4 | 390.0 |
| AC ra=0.05 | 49.5 | 8.2 | 121.5 | 390.0 |
| AC ra=0.2 | 47.0 | 8.4 | 114.7 | 390.0 |
| AC (preset, 0.6) | 44.1 | 8.8 | 107.1 | 388.3 |
| AC ra=1.5 | 41.9 | 9.4 | 101.3 | 377.5 |
| AC ra=20 | 38.7 | 11.1 | 92.8 | 164.6 |
| AC ra=5 | 39.8 | 10.2 | 96.1 | 265.5 |
| POV 10% | 46.1 | 10.8 | 108.3 | 259.0 |
| POV 12.5% | 43.6 | 10.3 | 103.8 | 208.3 |
| POV 15% | 42.0 | 10.5 | 100.4 | 168.2 |
| POV 17.5% | 40.8 | 10.9 | 97.5 | 138.6 |
| POV 20% | 39.8 | 11.4 | 95.1 | 116.3 |
| POV 22.5% | 39.1 | 11.9 | 93.1 | 99.6 |
| POV 25% | 38.5 | 12.3 | 91.4 | 86.6 |
| POV 5% | 60.4 | 21.1 | 127.1 | 368.9 |
| POV 7.5% | 50.9 | 13.2 | 115.5 | 318.1 |
| RL agent | 40.7 | 10.7 | 97.8 | 104.4 |

**Agent vs the best setting of each family.** The best setting for fold *k* is chosen on the other folds (leave-one-fold-out), so it is not fitted to the episodes it is scored on. `oracle` picks on all folds including the scored one and is the most generous possible benchmark.

| comparison | oracle pick | LOFO picks | saving vs LOFO (bps) | saving vs oracle (bps) | runs > 0 (LOFO) |
|---|---|---|---|---|---|
| clipped (old): best AC | AC ra=20 | AC ra=20 | -1.96 ± 0.79 | -1.96 ± 0.79 | 0/12 |
| clipped (old): best POV | POV 25% | POV 25% | -2.13 ± 0.88 | -2.13 ± 0.88 | 0/12 |
| signed IS: best AC | AC ra=0.01 | AC ra=0.01 | -2.49 ± 0.44 | -2.49 ± 0.44 | 0/12 |
| signed IS: best POV | POV 12.5% | POV 12.5% | -0.38 ± 0.57 | -0.38 ± 0.57 | 4/12 |

## 3. Cost-vs-risk frontier

Signed IS. x = standard deviation of per-episode cost (risk, computed within side and averaged), y = mean cost. Down and left is better. The AC curve is the classical efficient frontier traced by risk aversion; the POV curve by participation rate. See `frontier.png`.

RL agent (pooled over all runs): mean 10.7 bps, risk 98.8 bps. Single runs are each scored on one fold's test period, so they scatter with the period as well as the policy.

- Settings that are both cheaper AND less risky than the agent: AC ra=5
- Settings the agent beats on both: POV 10%, POV 5%, POV 7.5%

## 4. Where the cost comes from (signed IS decomposition)

bps, mean over all episodes. Buy and sell are averaged, so the drift column is ~0 by construction; its per-side size is shown separately.

| strategy | drift | own permanent | execution | fees | total | |drift| per side | drift std |
|---|---|---|---|---|---|---|---|
| TWAP | 0.00 | 5.00 | 2.78 | 0.43 | 8.21 | 0.53 | 125.22 |
| VWAP | -0.00 | 5.00 | 3.28 | 0.43 | 8.71 | 0.30 | 120.73 |
| AC (preset, 0.6) | -0.00 | 5.00 | 3.39 | 0.43 | 8.82 | 0.18 | 107.07 |
| POV 5% | 0.00 | 5.00 | 15.63 | 0.43 | 21.06 | 0.05 | 124.50 |
| POV 10% | 0.00 | 5.00 | 5.35 | 0.43 | 10.77 | 0.31 | 108.05 |
| POV 20% | 0.00 | 5.00 | 5.97 | 0.43 | 11.40 | 0.83 | 95.05 |
| RL agent | -0.02 | 5.00 | 5.32 | 0.40 | 10.70 | 0.82 | 98.74 |

## 5. Significance: day-clustered bootstrap

Paired difference benchmark − agent (bps), pooled over all runs. Episodes on the same ticker and day are correlated (same price path), so the bootstrap resamples whole ticker-days. CI is 99.38% (Bonferroni over 8 comparisons). The naive t-test treats every episode as independent and is shown for contrast.

| comparison | mean diff | CI | excludes 0 | ticker-days | naive p |
|---|---|---|---|---|---|
| clipped (old): TWAP | +10.13 | [+8.84, +11.57] | yes | 2272 | 0.0e+00 |
| clipped (old): VWAP | +9.16 | [+7.90, +10.49] | yes | 2272 | 0.0e+00 |
| clipped (old): AC (preset, 0.6) | +3.49 | [+2.91, +4.14] | yes | 2272 | 2.0e-212 |
| clipped (old): POV 5% | +19.74 | [+17.84, +21.60] | yes | 2272 | 0.0e+00 |
| clipped (old): POV 10% | +5.43 | [+4.59, +6.38] | yes | 2272 | 8.5e-283 |
| clipped (old): POV 20% | -0.81 | [-1.28, -0.33] | yes | 2272 | 1.8e-22 |
| clipped (old): AC ra=20 (best) | -1.96 | [-2.34, -1.62] | yes | 2272 | 4.8e-182 |
| clipped (old): POV 25% (best) | -2.13 | [-2.64, -1.65] | yes | 2272 | 5.8e-111 |
| signed IS: TWAP | -2.49 | [-2.64, -2.33] | yes | 2272 | 1.7e-11 |
| signed IS: VWAP | -1.99 | [-2.13, -1.85] | yes | 2272 | 3.8e-09 |
| signed IS: AC (preset, 0.6) | -1.88 | [-1.99, -1.76] | yes | 2272 | 5.8e-28 |
| signed IS: POV 5% | +10.37 | [+8.84, +12.08] | yes | 2272 | 2.7e-129 |
| signed IS: POV 10% | +0.08 | [-0.37, +0.58] | NO | 2272 | 7.3e-01 |
| signed IS: POV 20% | +0.71 | [+0.54, +0.86] | yes | 2272 | 2.7e-08 |
| signed IS: AC ra=0.01 (best) | -2.49 | [-2.64, -2.36] | yes | 2272 | 5.1e-12 |
| signed IS: POV 12.5% (best) | -0.38 | [-0.64, -0.11] | yes | 2272 | 2.9e-02 |

## 6. What the agent does

From per-step traces. Participation = shares filled / bar volume, only over steps where the order was still open. See `behaviour.png`.

| agent participation % by quintile of | Q1 | Q2 | Q3 | Q4 | Q5 |
|---|---|---|---|---|---|
| prev-bar volume | 24.7 | 24.8 | 24.8 | 24.5 | 14.9 |
| prev-bar spread | 23.4 | 23.4 | 22.9 | 22.1 | 21.9 |
| price vs arrival | 22.4 | 23.0 | 22.5 | 23.1 | 22.8 |
| alpha signal |  |  |  |  |  |

Agent participation: calm regime 22.4%, volatile regime 23.7%. Mean passive fraction of its orders: 10.4%.

Step-by-step correlation of agent and POV 20% participation (same episodes): 0.85.
