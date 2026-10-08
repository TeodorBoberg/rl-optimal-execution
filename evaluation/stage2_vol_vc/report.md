# Batch 1 report

Run configuration: `overrides: market.permanent_impact_mode=cumulative, market.impact_volume_ref=bar, reward_weights.disable_alpha_signal=true, execution.enable_passive=false, execution.action_squash=sigmoid, execution.drop_noise_obs=true`

Folds [3]; 500 paired episodes per fold and side; 3 trained policies. Every strategy in an episode trades the same ticker and day.

## 0. Metric check: clipped vs signed cost

Mean cost in bps, averaged over all folds and both sides. The clipped metric charges adverse drift and never credits favourable drift; `drift charge` is how much of the old number that asymmetry accounts for.

| strategy | clipped (old) | signed IS | drift charge | finish step | done by 25% |
|---|---|---|---|---|---|
| TWAP | 58.3 | 8.8 | 49.4 | 390.0 | 24.7 |
| VWAP | 56.9 | 9.0 | 48.0 | 390.0 | 32.4 |
| AC (preset, 0.6) | 50.4 | 9.3 | 41.1 | 388.2 | 59.7 |
| POV 5% | 63.4 | 15.0 | 48.4 | 371.3 | 27.8 |
| POV 10% | 51.6 | 9.6 | 42.0 | 258.1 | 54.4 |
| POV 20% | 44.7 | 10.5 | 34.1 | 112.8 | 87.3 |
| RL agent | 49.6 | 8.9 | 40.7 | 341.0 | 56.5 |

## 1. Headline: agent vs benchmarks, 3 runs

**Old metric (clipped)**: % cost reduction, mean ± std across runs. This should reproduce the published table.

| vs | buy | sell | buy+sell | runs > 0 |
|---|---|---|---|---|
| TWAP | +14.8 ± 0.6 | +15.1 ± 1.3 | +14.9 ± 0.7 | 3/3 |
| VWAP | +13.1 ± 0.7 | +12.7 ± 1.3 | +12.9 ± 0.7 | 3/3 |
| AC (preset, 0.6) | +2.8 ± 0.7 | +0.1 ± 1.5 | +1.6 ± 0.8 | 3/3 |
| POV 5% | +22.5 ± 0.6 | +20.8 ± 1.2 | +21.8 ± 0.6 | 3/3 |
| POV 10% | +6.2 ± 0.7 | +0.9 ± 1.5 | +3.9 ± 0.8 | 3/3 |
| POV 20% | -9.2 ± 0.8 | -13.3 ± 1.7 | -10.9 ± 0.9 | 0/3 |

**Signed implementation shortfall**: cost saved in **bps** (benchmark − agent), mean ± std across runs. Percentages are not used because signed means can sit near zero. `buy+sell` averages each run's buy and sell results; buy and sell episodes share days, so market drift cancels exactly and what remains is execution.

| vs | buy | sell | buy+sell | runs > 0 |
|---|---|---|---|---|
| TWAP | +1.6 ± 0.0 | -1.7 ± 0.2 | -0.0 ± 0.1 | 1/3 |
| VWAP | +1.7 ± 0.0 | -1.6 ± 0.2 | +0.1 ± 0.1 | 2/3 |
| AC (preset, 0.6) | +1.4 ± 0.0 | -0.5 ± 0.2 | +0.5 ± 0.1 | 3/3 |
| POV 5% | +9.4 ± 0.0 | +2.8 ± 0.2 | +6.1 ± 0.1 | 3/3 |
| POV 10% | +3.1 ± 0.0 | -1.8 ± 0.2 | +0.7 ± 0.1 | 3/3 |
| POV 20% | +1.3 ± 0.0 | +2.0 ± 0.2 | +1.7 ± 0.1 | 3/3 |

## 2. Benchmark sweep: is the agent better than the best setting?

Mean cost (bps) at every setting, all folds and sides.

| setting | clipped | signed | signed std | finish step |
|---|---|---|---|---|
| TWAP | 58.3 | 8.8 | 132.6 | 390.0 |
| VWAP | 56.9 | 9.0 | 127.1 | 390.0 |
| AC ra=0.01 | 57.9 | 8.8 | 131.6 | 390.0 |
| AC ra=0.05 | 56.8 | 8.9 | 128.4 | 390.0 |
| AC ra=0.2 | 53.9 | 9.0 | 120.5 | 390.0 |
| AC ra=0.3 | 52.6 | 9.1 | 117.3 | 389.3 |
| AC (preset, 0.6) | 50.4 | 9.3 | 111.7 | 388.2 |
| AC ra=1 | 48.8 | 9.6 | 107.9 | 385.1 |
| AC ra=1.5 | 47.7 | 9.8 | 105.2 | 377.2 |
| AC ra=10 | 44.1 | 10.6 | 96.9 | 203.2 |
| AC ra=2.5 | 46.4 | 10.0 | 102.2 | 342.8 |
| AC ra=20 | 43.6 | 10.8 | 95.6 | 162.3 |
| AC ra=5 | 45.1 | 10.3 | 99.1 | 263.6 |
| POV 10% | 51.6 | 9.6 | 114.7 | 258.1 |
| POV 12.5% | 49.1 | 9.5 | 109.4 | 206.8 |
| POV 15% | 47.2 | 9.8 | 105.1 | 165.5 |
| POV 17.5% | 45.8 | 10.2 | 101.5 | 135.4 |
| POV 20% | 44.7 | 10.5 | 98.8 | 112.8 |
| POV 22.5% | 43.8 | 10.9 | 96.5 | 96.5 |
| POV 25% | 43.0 | 11.3 | 94.5 | 83.8 |
| POV 5% | 63.4 | 15.0 | 132.4 | 371.3 |
| POV 7.5% | 55.9 | 10.8 | 122.5 | 319.6 |
| AC-volclock ra=0.01 | 56.5 | 9.0 | 126.0 | 390.0 |
| AC-volclock ra=0.2 | 51.6 | 9.2 | 113.2 | 390.0 |
| AC-volclock ra=0.6 | 47.9 | 9.6 | 104.4 | 390.0 |
| AC-volclock ra=1.5 | 45.5 | 10.1 | 99.3 | 389.5 |
| AC-volclock ra=20 | 43.2 | 10.9 | 94.9 | 170.8 |
| AC-volclock ra=5 | 43.8 | 10.6 | 96.0 | 307.6 |
| AC-live ra=0.01 | 56.0 | 8.9 | 124.3 | 389.9 |
| AC-live ra=0.05 | 54.7 | 8.9 | 120.9 | 389.9 |
| AC-live ra=0.2 | 51.8 | 9.0 | 113.5 | 389.9 |
| AC-live ra=0.6 | 48.0 | 9.4 | 104.4 | 388.9 |
| AC-live ra=1 | 46.0 | 9.8 | 99.9 | 384.2 |
| AC-live ra=1.5 | 44.9 | 10.1 | 97.5 | 375.8 |
| AC-live ra=10 | 43.1 | 10.8 | 94.7 | 251.1 |
| AC-live ra=2.5 | 44.1 | 10.3 | 95.9 | 356.5 |
| AC-live ra=20 | 43.0 | 11.0 | 94.5 | 198.9 |
| AC-live ra=5 | 43.4 | 10.6 | 95.0 | 308.9 |
| RL agent | 49.6 | 8.9 | 109.6 | 341.0 |

**Agent vs the best setting of each family.** The best setting for fold *k* is chosen on the other folds (leave-one-fold-out), so it is not fitted to the episodes it is scored on. `oracle` picks on all folds including the scored one and is the most generous possible benchmark.

| comparison | oracle pick | LOFO picks | saving vs LOFO (bps) | saving vs oracle (bps) | runs > 0 (LOFO) |
|---|---|---|---|---|---|
| clipped (old): best AC | AC ra=20 | AC ra=20 | -6.02 ± 0.40 | -6.02 ± 0.40 | 0/3 |
| clipped (old): best POV | POV 25% | POV 25% | -6.56 ± 0.40 | -6.56 ± 0.40 | 0/3 |
| clipped (old): best AC volume clock (live) | AC-live ra=20 | AC-live ra=20 | -6.57 ± 0.40 | -6.57 ± 0.40 | 0/3 |
| signed IS: best AC | AC ra=0.01 | AC ra=0.01 | -0.05 ± 0.10 | -0.05 ± 0.10 | 1/3 |
| signed IS: best POV | POV 12.5% | POV 12.5% | +0.64 ± 0.10 | +0.64 ± 0.10 | 3/3 |
| signed IS: best AC volume clock (live) | AC-live ra=0.05 | AC-live ra=0.05 | -0.01 ± 0.10 | -0.01 ± 0.10 | 2/3 |

## 3. Cost-vs-risk frontier

Signed IS. x = standard deviation of per-episode cost (risk, computed within side and averaged), y = mean cost. Down and left is better. The AC curve is the classical efficient frontier traced by risk aversion; the POV curve by participation rate. See `frontier.png`.

RL agent (pooled over all runs): mean 8.9 bps, risk 109.6 bps. Single runs are each scored on one fold's test period, so they scatter with the period as well as the policy.

- Settings that are both cheaper AND less risky than the agent: none
- Settings the agent beats on both: AC ra=0.2, AC ra=0.3, AC (preset, 0.6), AC-live ra=0.01, AC-live ra=0.2, AC-volclock ra=0.01, AC-volclock ra=0.2, POV 10%, POV 5%, POV 7.5%, VWAP

## 4. Where the cost comes from (signed IS decomposition)

bps, mean over all episodes. Buy and sell are averaged, so the drift column is ~0 by construction; its per-side size is shown separately.

| strategy | drift | own permanent | execution | fees | total | |drift| per side | drift std |
|---|---|---|---|---|---|---|---|
| TWAP | 0.00 | 5.00 | 3.43 | 0.42 | 8.85 | 13.65 | 132.59 |
| VWAP | 0.00 | 5.00 | 3.54 | 0.42 | 8.95 | 13.64 | 127.14 |
| AC (preset, 0.6) | 0.00 | 5.00 | 3.93 | 0.42 | 9.35 | 12.89 | 111.72 |
| POV 5% | -0.00 | 5.00 | 9.61 | 0.42 | 15.02 | 15.28 | 131.51 |
| POV 10% | -0.00 | 5.00 | 4.17 | 0.42 | 9.58 | 14.41 | 114.64 |
| POV 20% | 0.00 | 5.00 | 5.13 | 0.42 | 10.55 | 11.57 | 98.76 |
| RL agent | -0.01 | 5.00 | 3.49 | 0.42 | 8.89 | 11.94 | 109.56 |

## 5. Significance: day-clustered bootstrap

Paired difference benchmark − agent (bps), pooled over all runs. Episodes on the same ticker and day are correlated (same price path), so the bootstrap resamples whole ticker-days. CI is 99.44% (Bonferroni over 9 comparisons). The naive t-test treats every episode as independent and is shown for contrast.

| comparison | mean diff | CI | excludes 0 | ticker-days | naive p |
|---|---|---|---|---|---|
| clipped (old): TWAP | +8.71 | [+6.88, +10.47] | yes | 374 | 2.3e-91 |
| clipped (old): VWAP | +7.37 | [+5.77, +9.02] | yes | 374 | 8.4e-89 |
| clipped (old): AC (preset, 0.6) | +0.83 | [+0.05, +1.49] | yes | 374 | 1.1e-08 |
| clipped (old): POV 5% | +13.81 | [+11.11, +16.56] | yes | 374 | 1.9e-130 |
| clipped (old): POV 10% | +2.04 | [+0.71, +3.33] | yes | 374 | 8.0e-16 |
| clipped (old): POV 20% | -4.89 | [-6.69, -3.11] | yes | 374 | 2.4e-36 |
| clipped (old): AC ra=20 (best) | -6.02 | [-7.88, -4.16] | yes | 374 | 1.0e-48 |
| clipped (old): POV 25% (best) | -6.56 | [-8.73, -4.59] | yes | 374 | 2.2e-45 |
| clipped (old): AC-live ra=20 (best) | -6.57 | [-8.71, -4.54] | yes | 374 | 1.4e-48 |
| signed IS: TWAP | -0.04 | [-0.20, +0.10] | NO | 374 | 9.5e-01 |
| signed IS: VWAP | +0.06 | [-0.10, +0.23] | NO | 374 | 9.1e-01 |
| signed IS: AC (preset, 0.6) | +0.46 | [+0.30, +0.62] | yes | 374 | 3.7e-02 |
| signed IS: POV 5% | +6.13 | [+4.13, +8.27] | yes | 374 | 8.4e-15 |
| signed IS: POV 10% | +0.69 | [+0.30, +1.18] | yes | 374 | 6.1e-02 |
| signed IS: POV 20% | +1.66 | [+1.43, +1.87] | yes | 374 | 6.2e-03 |
| signed IS: AC ra=0.01 (best) | -0.05 | [-0.20, +0.11] | NO | 374 | 9.4e-01 |
| signed IS: POV 12.5% (best) | +0.64 | [+0.42, +0.90] | yes | 374 | 9.2e-02 |
| signed IS: AC-live ra=0.05 (best) | -0.01 | [-0.20, +0.22] | NO | 374 | 9.9e-01 |

## 6. What the agent does

From per-step traces. Participation = shares filled / bar volume, only over steps where the order was still open. See `behaviour.png`.

| agent participation % by quintile of | Q1 | Q2 | Q3 | Q4 | Q5 |
|---|---|---|---|---|---|
| prev-bar volume | 10.4 | 9.0 | 8.2 | 7.2 | 6.2 |
| prev-bar spread | 9.5 | 8.7 | 7.7 | 8.9 | 6.2 |
| price vs arrival | 7.0 | 9.4 | 10.2 | 7.6 | 6.8 |
| alpha signal |  |  |  |  |  |

Agent participation: calm regime 9.9%, volatile regime 4.6%. Mean passive fraction of its orders: 0.0%.

Step-by-step correlation of agent and POV 20% participation (same episodes): 0.53.
