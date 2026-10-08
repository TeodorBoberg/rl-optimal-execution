# Batch 1 report

Run configuration: `overrides: market.permanent_impact_mode=cumulative, market.impact_volume_ref=bar, reward_weights.disable_alpha_signal=true, execution.enable_passive=false, execution.action_squash=sigmoid, execution.drop_noise_obs=true, execution.honest_obs=true`

Folds [0, 1, 2, 3]; 400 paired episodes per fold and side; 12 trained policies. Every strategy in an episode trades the same ticker and day.

## 0. Metric check: clipped vs signed cost

Mean cost in bps, averaged over all folds and both sides. The clipped metric charges adverse drift and never credits favourable drift; `drift charge` is how much of the old number that asymmetry accounts for.

| strategy | clipped (old) | signed IS | drift charge | finish step | done by 25% |
|---|---|---|---|---|---|
| TWAP | 50.9 | 8.7 | 42.2 | 390.0 | 24.7 |
| VWAP | 49.7 | 8.8 | 40.9 | 390.0 | 32.3 |
| AC (preset, 0.6) | 44.1 | 9.2 | 35.0 | 388.3 | 59.4 |
| POV 5% | 55.8 | 15.0 | 40.7 | 368.6 | 28.1 |
| POV 10% | 44.9 | 9.6 | 35.3 | 259.8 | 53.7 |
| POV 20% | 38.9 | 10.2 | 28.7 | 117.7 | 86.1 |
| RL agent | 43.8 | 8.8 | 34.9 | 323.5 | 55.0 |

## 1. Headline: agent vs benchmarks, 12 runs

**Old metric (clipped)**: % cost reduction, mean ± std across runs. This should reproduce the published table.

| vs | buy | sell | buy+sell | runs > 0 |
|---|---|---|---|---|
| TWAP | +14.2 ± 2.8 | +13.8 ± 3.9 | +14.0 ± 3.2 | 12/12 |
| VWAP | +11.9 ± 3.0 | +11.9 ± 3.8 | +11.9 ± 3.2 | 12/12 |
| AC (preset, 0.6) | +0.7 ± 3.5 | +0.8 ± 3.9 | +0.8 ± 3.4 | 8/12 |
| POV 5% | +20.9 ± 4.5 | +20.8 ± 5.4 | +20.9 ± 4.7 | 12/12 |
| POV 10% | +2.4 ± 4.3 | +1.7 ± 3.7 | +2.2 ± 3.3 | 9/12 |
| POV 20% | -13.1 ± 4.8 | -12.5 ± 2.9 | -12.8 ± 3.4 | 0/12 |

**Signed implementation shortfall**: cost saved in **bps** (benchmark − agent), mean ± std across runs. Percentages are not used because signed means can sit near zero. `buy+sell` averages each run's buy and sell results; buy and sell episodes share days, so market drift cancels exactly and what remains is execution.

| vs | buy | sell | buy+sell | runs > 0 |
|---|---|---|---|---|
| TWAP | +1.1 ± 1.0 | -1.3 ± 1.0 | -0.1 ± 0.2 | 4/12 |
| VWAP | +0.8 ± 1.1 | -0.9 ± 1.1 | -0.0 ± 0.2 | 7/12 |
| AC (preset, 0.6) | +0.4 ± 1.0 | +0.2 ± 0.8 | +0.3 ± 0.2 | 11/12 |
| POV 5% | +7.2 ± 2.4 | +5.1 ± 4.4 | +6.2 ± 2.5 | 12/12 |
| POV 10% | +1.3 ± 1.5 | +0.2 ± 2.0 | +0.8 ± 0.5 | 11/12 |
| POV 20% | +0.6 ± 0.5 | +2.0 ± 0.9 | +1.3 ± 0.4 | 12/12 |

## 2. Benchmark sweep: is the agent better than the best setting?

Mean cost (bps) at every setting, all folds and sides.

| setting | clipped | signed | signed std | finish step |
|---|---|---|---|---|
| TWAP | 50.9 | 8.7 | 122.8 | 390.0 |
| VWAP | 49.7 | 8.8 | 118.2 | 390.0 |
| AC ra=0.01 | 50.6 | 8.7 | 122.0 | 390.0 |
| AC ra=0.05 | 49.6 | 8.7 | 119.1 | 390.0 |
| AC ra=0.2 | 47.1 | 8.8 | 112.2 | 390.0 |
| AC ra=0.3 | 46.1 | 8.9 | 109.4 | 389.4 |
| AC (preset, 0.6) | 44.1 | 9.2 | 104.4 | 388.3 |
| AC ra=1 | 42.8 | 9.4 | 101.1 | 385.3 |
| AC ra=1.5 | 41.8 | 9.5 | 98.7 | 377.6 |
| AC ra=10 | 38.7 | 10.2 | 91.3 | 206.3 |
| AC ra=2.5 | 40.7 | 9.7 | 96.1 | 344.3 |
| AC ra=20 | 38.2 | 10.4 | 90.0 | 165.6 |
| AC ra=5 | 39.5 | 10.0 | 93.3 | 266.3 |
| POV 10% | 44.9 | 9.6 | 104.9 | 259.8 |
| POV 12.5% | 42.6 | 9.4 | 100.6 | 209.7 |
| POV 15% | 41.0 | 9.6 | 97.1 | 169.9 |
| POV 17.5% | 39.8 | 9.9 | 94.4 | 140.2 |
| POV 20% | 38.9 | 10.2 | 92.1 | 117.7 |
| POV 22.5% | 38.1 | 10.5 | 90.2 | 100.9 |
| POV 25% | 37.5 | 10.8 | 88.6 | 87.7 |
| POV 5% | 55.8 | 15.0 | 122.2 | 368.6 |
| POV 7.5% | 48.8 | 11.0 | 111.6 | 318.4 |
| AC-volclock ra=0.01 | 49.4 | 8.8 | 117.2 | 390.0 |
| AC-volclock ra=0.2 | 45.2 | 9.0 | 105.8 | 390.0 |
| AC-volclock ra=0.6 | 42.0 | 9.4 | 98.0 | 390.0 |
| AC-volclock ra=1.5 | 39.9 | 9.8 | 93.4 | 389.5 |
| AC-volclock ra=20 | 37.7 | 10.5 | 89.0 | 174.9 |
| AC-volclock ra=5 | 38.4 | 10.2 | 90.2 | 310.4 |
| AC-live ra=0.01 | 48.8 | 8.7 | 115.5 | 389.9 |
| AC-live ra=0.05 | 47.5 | 8.7 | 111.7 | 389.9 |
| AC-live ra=0.2 | 44.9 | 8.8 | 104.6 | 389.8 |
| AC-live ra=0.6 | 41.7 | 9.2 | 96.7 | 386.7 |
| AC-live ra=1 | 40.0 | 9.5 | 92.9 | 381.4 |
| AC-live ra=1.5 | 39.1 | 9.7 | 91.0 | 372.8 |
| AC-live ra=10 | 37.6 | 10.4 | 88.8 | 252.6 |
| AC-live ra=2.5 | 38.4 | 10.0 | 89.7 | 354.0 |
| AC-live ra=20 | 37.5 | 10.5 | 88.7 | 202.2 |
| AC-live ra=5 | 37.9 | 10.2 | 89.0 | 308.1 |
| AC-live spread k=0.5 ra=0.01 | 48.2 | 8.6 | 114.3 | 390.0 |
| AC-live spread k=0.5 ra=0.05 | 47.0 | 8.6 | 110.5 | 390.0 |
| AC-live spread k=0.5 ra=0.2 | 44.3 | 8.8 | 103.6 | 389.7 |
| AC-live spread k=0.5 ra=0.6 | 41.2 | 9.2 | 96.0 | 385.0 |
| AC-live spread k=0.5 ra=1.5 | 38.8 | 9.7 | 90.6 | 366.6 |
| AC-live spread k=0.5 ra=20 | 37.5 | 10.5 | 88.7 | 184.8 |
| AC-live spread k=0.5 ra=5 | 37.8 | 10.2 | 89.0 | 288.9 |
| AC-live spread k=1 ra=0.01 | 47.6 | 8.6 | 112.9 | 390.0 |
| AC-live spread k=1 ra=0.05 | 46.3 | 8.6 | 109.2 | 390.0 |
| AC-live spread k=1 ra=0.2 | 43.7 | 8.8 | 102.5 | 389.2 |
| AC-live spread k=1 ra=0.6 | 40.8 | 9.2 | 95.3 | 382.2 |
| AC-live spread k=1 ra=1.5 | 38.6 | 9.8 | 90.4 | 355.9 |
| AC-live spread k=1 ra=20 | 37.5 | 10.5 | 88.7 | 167.9 |
| AC-live spread k=1 ra=5 | 37.7 | 10.2 | 89.0 | 264.6 |
| AC-live spread k=2 ra=0.01 | 46.1 | 8.7 | 109.9 | 389.6 |
| AC-live spread k=2 ra=0.05 | 44.9 | 8.7 | 106.5 | 389.4 |
| AC-live spread k=2 ra=0.2 | 42.6 | 8.9 | 100.6 | 385.8 |
| AC-live spread k=2 ra=0.6 | 40.1 | 9.4 | 94.3 | 365.8 |
| AC-live spread k=2 ra=1.5 | 38.3 | 9.9 | 90.1 | 310.7 |
| AC-live spread k=2 ra=20 | 37.5 | 10.5 | 88.8 | 140.0 |
| AC-live spread k=2 ra=5 | 37.6 | 10.3 | 89.1 | 213.3 |
| RL agent | 43.8 | 8.8 | 103.0 | 323.5 |

**Agent vs the best setting of each family.** The best setting for fold *k* is chosen on the other folds (leave-one-fold-out), so it is not fitted to the episodes it is scored on. `oracle` picks on all folds including the scored one and is the most generous possible benchmark.

| comparison | oracle pick | LOFO picks | saving vs LOFO (bps) | saving vs oracle (bps) | runs > 0 (LOFO) |
|---|---|---|---|---|---|
| clipped (old): best AC | AC ra=20 | AC ra=20 | -5.60 ± 1.08 | -5.60 ± 1.08 | 0/12 |
| clipped (old): best POV | POV 25% | POV 25% | -6.27 ± 1.14 | -6.27 ± 1.14 | 0/12 |
| clipped (old): best AC volume clock (live) | AC-live ra=20 | AC-live ra=20 | -6.24 ± 1.13 | -6.24 ± 1.13 | 0/12 |
| clipped (old): best AC live, spread-aware | AC-live spread k=1 ra=20 | AC-live spread k=1 ra=20 | -6.29 ± 1.13 | -6.29 ± 1.13 | 0/12 |
| signed IS: best AC | AC ra=0.05 | AC ra=0.01, AC ra=0.05 | -0.11 ± 0.24 | -0.11 ± 0.24 | 4/12 |
| signed IS: best POV | POV 12.5% | POV 12.5% | +0.56 ± 0.40 | +0.56 ± 0.40 | 11/12 |
| signed IS: best AC volume clock (live) | AC-live ra=0.05 | AC-live ra=0.05 | -0.11 ± 0.26 | -0.11 ± 0.26 | 3/12 |
| signed IS: best AC live, spread-aware | AC-live spread k=1 ra=0.01 | AC-live spread k=1 ra=0.01 | -0.25 ± 0.26 | -0.25 ± 0.26 | 1/12 |

## 3. Cost-vs-risk frontier

Signed IS. x = standard deviation of per-episode cost (risk, computed within side and averaged), y = mean cost. Down and left is better. The AC curve is the classical efficient frontier traced by risk aversion; the POV curve by participation rate. See `frontier.png`.

RL agent (pooled over all runs): mean 8.8 bps, risk 103.6 bps. Single runs are each scored on one fold's test period, so they scatter with the period as well as the policy.

- Settings that are both cheaper AND less risky than the agent: AC-live spread k=1 ra=0.2
- Settings the agent beats on both: AC ra=0.2, AC ra=0.3, AC (preset, 0.6), AC-volclock ra=0.2, POV 10%, POV 5%, POV 7.5%

## 4. Where the cost comes from (signed IS decomposition)

bps, mean over all episodes. Buy and sell are averaged, so the drift column is ~0 by construction; its per-side size is shown separately.

| strategy | drift | own permanent | execution | fees | total | |drift| per side | drift std |
|---|---|---|---|---|---|---|---|
| TWAP | 0.00 | 5.00 | 3.30 | 0.43 | 8.73 | 6.05 | 122.83 |
| VWAP | -0.00 | 5.00 | 3.40 | 0.43 | 8.83 | 5.67 | 118.18 |
| AC (preset, 0.6) | 0.00 | 5.00 | 3.72 | 0.43 | 9.15 | 4.94 | 104.43 |
| POV 5% | 0.00 | 5.00 | 9.59 | 0.43 | 15.02 | 5.88 | 120.95 |
| POV 10% | -0.00 | 5.00 | 4.16 | 0.43 | 9.59 | 5.34 | 104.84 |
| POV 20% | 0.00 | 5.00 | 4.75 | 0.43 | 10.18 | 4.12 | 92.07 |
| RL agent | 0.01 | 5.00 | 3.40 | 0.43 | 8.84 | 4.84 | 103.56 |

## 5. Significance: day-clustered bootstrap

Paired difference benchmark − agent (bps), pooled over all runs. Episodes on the same ticker and day are correlated (same price path), so the bootstrap resamples whole ticker-days. CI is 99.50% (Bonferroni over 10 comparisons). The naive t-test treats every episode as independent and is shown for contrast.

| comparison | mean diff | CI | excludes 0 | ticker-days | naive p |
|---|---|---|---|---|---|
| clipped (old): TWAP | +7.19 | [+6.19, +8.20] | yes | 1256 | 4.4e-214 |
| clipped (old): VWAP | +5.96 | [+5.00, +6.87] | yes | 1256 | 2.0e-190 |
| clipped (old): AC (preset, 0.6) | +0.38 | [-0.09, +0.81] | NO | 1256 | 1.2e-04 |
| clipped (old): POV 5% | +12.00 | [+10.35, +13.60] | yes | 1256 | 0.0e+00 |
| clipped (old): POV 10% | +1.12 | [+0.41, +1.85] | yes | 1256 | 1.0e-14 |
| clipped (old): POV 20% | -4.87 | [-5.88, -3.87] | yes | 1256 | 2.6e-108 |
| clipped (old): AC ra=20 (best) | -5.60 | [-6.55, -4.52] | yes | 1256 | 2.8e-138 |
| clipped (old): POV 25% (best) | -6.27 | [-7.45, -5.13] | yes | 1256 | 2.0e-129 |
| clipped (old): AC-live ra=20 (best) | -6.24 | [-7.41, -5.09] | yes | 1256 | 6.6e-137 |
| clipped (old): AC-live spread k=1 ra=20 (best) | -6.29 | [-7.36, -5.20] | yes | 1256 | 6.1e-137 |
| signed IS: TWAP | -0.11 | [-0.30, +0.03] | NO | 1256 | 7.6e-01 |
| signed IS: VWAP | -0.01 | [-0.19, +0.13] | NO | 1256 | 9.7e-01 |
| signed IS: AC (preset, 0.6) | +0.31 | [+0.12, +0.47] | yes | 1256 | 2.8e-02 |
| signed IS: POV 5% | +6.18 | [+4.91, +7.60] | yes | 1256 | 2.1e-49 |
| signed IS: POV 10% | +0.75 | [+0.47, +1.07] | yes | 1256 | 2.5e-04 |
| signed IS: POV 20% | +1.34 | [+1.15, +1.52] | yes | 1256 | 5.5e-05 |
| signed IS: AC ra=0.05 (best) | -0.11 | [-0.29, +0.02] | NO | 1256 | 7.0e-01 |
| signed IS: POV 12.5% (best) | +0.56 | [+0.34, +0.79] | yes | 1256 | 1.0e-02 |
| signed IS: AC-live ra=0.05 (best) | -0.11 | [-0.32, +0.04] | NO | 1256 | 6.0e-01 |
| signed IS: AC-live spread k=1 ra=0.01 (best) | -0.25 | [-0.44, -0.07] | yes | 1256 | 2.4e-01 |

## 6. What the agent does

From per-step traces. Participation = shares filled / bar volume, only over steps where the order was still open. See `behaviour.png`.

| agent participation % by quintile of | Q1 | Q2 | Q3 | Q4 | Q5 |
|---|---|---|---|---|---|
| prev-bar volume | 10.4 | 9.3 | 8.6 | 8.0 | 7.1 |
| prev-bar spread | 9.2 | 8.3 | 8.7 | 9.8 | 7.3 |
| price vs arrival | 7.3 | 9.4 | 10.3 | 8.5 | 7.8 |
| alpha signal |  |  |  |  |  |

Agent participation: calm regime nan%, volatile regime 9.5%. Mean passive fraction of its orders: 0.0%.

Step-by-step correlation of agent and POV 20% participation (same episodes): 0.55.
