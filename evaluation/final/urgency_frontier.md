# RL urgency frontier vs Almgren-Chriss

Run configuration: `overrides: market.permanent_impact_mode=cumulative, market.impact_volume_ref=bar, reward_weights.disable_alpha_signal=true, execution.enable_passive=false, execution.action_squash=sigmoid, execution.drop_noise_obs=true, execution.honest_obs=true`

Pairing with the benchmark episodes: PASS. Signed implementation shortfall. Risk = std of per-episode cost within side, averaged over sides.

## Pooled over all folds and runs

| strategy | risk (bps) | mean cost (bps) | finish step | done by 25% |
|---|---|---|---|---|
| RL urgency 0 | 119.4 | 10.30 | 384 | 33% |
| RL urgency 0.25 | 111.2 | 9.10 | 367 | 43% |
| RL urgency 0.5 | 103.6 | 8.84 | 323 | 55% |
| RL urgency 0.75 | 97.8 | 9.06 | 268 | 66% |
| RL urgency 1 | 94.1 | 9.43 | 209 | 76% |
| twap | 122.8 | 8.73 | 390 | 25% |
| vwap | 118.2 | 8.83 | 390 | 32% |
| ac@0.01 | 122.0 | 8.73 | 390 | 26% |
| ac@0.05 | 119.1 | 8.73 | 390 | 31% |
| ac@0.2 | 112.2 | 8.84 | 390 | 44% |
| ac@0.3 | 109.4 | 8.93 | 389 | 49% |
| ac@0.6 | 104.4 | 9.15 | 388 | 59% |
| ac@1 | 101.1 | 9.36 | 385 | 67% |
| ac@1.5 | 98.7 | 9.53 | 378 | 73% |
| ac@2.5 | 96.1 | 9.74 | 344 | 79% |
| ac@5 | 93.3 | 10.00 | 266 | 85% |
| ac@10 | 91.3 | 10.22 | 206 | 89% |
| ac@20 | 90.0 | 10.40 | 166 | 91% |
| acv@0.01 | 117.2 | 8.83 | 390 | 34% |
| acv@0.2 | 105.8 | 9.03 | 390 | 52% |
| acv@0.6 | 98.0 | 9.40 | 390 | 67% |
| acv@1.5 | 93.4 | 9.78 | 390 | 78% |
| acv@5 | 90.2 | 10.21 | 310 | 87% |
| acv@20 | 89.0 | 10.51 | 175 | 91% |
| acl@0.01 | 115.5 | 8.73 | 390 | 36% |
| acl@0.05 | 111.7 | 8.73 | 390 | 41% |
| acl@0.2 | 104.6 | 8.83 | 390 | 51% |
| acl@0.6 | 96.7 | 9.18 | 387 | 65% |
| acl@1 | 92.9 | 9.50 | 381 | 73% |
| acl@1.5 | 91.0 | 9.74 | 373 | 78% |
| acl@2.5 | 89.7 | 9.98 | 354 | 83% |
| acl@5 | 89.0 | 10.23 | 308 | 87% |
| acl@10 | 88.8 | 10.41 | 253 | 90% |
| acl@20 | 88.7 | 10.52 | 202 | 91% |
| pov@5 | 122.2 | 15.02 | 369 | 28% |
| pov@7.5 | 111.6 | 10.97 | 318 | 41% |
| pov@10 | 104.9 | 9.59 | 260 | 54% |
| pov@12.5 | 100.6 | 9.40 | 210 | 65% |
| pov@15 | 97.1 | 9.59 | 170 | 74% |
| pov@17.5 | 94.4 | 9.88 | 140 | 81% |
| pov@20 | 92.1 | 10.18 | 118 | 86% |
| pov@22.5 | 90.2 | 10.50 | 101 | 90% |
| pov@25 | 88.6 | 10.81 | 88 | 93% |
| acs0.5@0.01 | 114.3 | 8.63 | 390 | 39% |
| acs0.5@0.05 | 110.5 | 8.64 | 390 | 43% |
| acs0.5@0.2 | 103.6 | 8.76 | 390 | 54% |
| acs0.5@0.6 | 96.0 | 9.15 | 385 | 68% |
| acs0.5@1.5 | 90.6 | 9.73 | 367 | 80% |
| acs0.5@5 | 89.0 | 10.23 | 289 | 88% |
| acs0.5@20 | 88.7 | 10.53 | 185 | 92% |
| acs1@0.01 | 112.9 | 8.59 | 390 | 42% |
| acs1@0.05 | 109.2 | 8.62 | 390 | 46% |
| acs1@0.2 | 102.5 | 8.77 | 389 | 57% |
| acs1@0.6 | 95.3 | 9.20 | 382 | 71% |
| acs1@1.5 | 90.4 | 9.76 | 356 | 82% |
| acs1@5 | 89.0 | 10.23 | 265 | 89% |
| acs1@20 | 88.7 | 10.52 | 168 | 92% |
| acs2@0.01 | 109.9 | 8.66 | 390 | 49% |
| acs2@0.05 | 106.5 | 8.71 | 389 | 54% |
| acs2@0.2 | 100.6 | 8.93 | 386 | 64% |
| acs2@0.6 | 94.3 | 9.37 | 366 | 76% |
| acs2@1.5 | 90.1 | 9.88 | 311 | 85% |
| acs2@5 | 89.1 | 10.27 | 213 | 90% |
| acs2@20 | 88.8 | 10.51 | 140 | 92% |

## Agent vs each benchmark family at equal risk, per run

Agent mean cost minus the family's mean cost at the same risk, interpolated along the lower convex hull of that fold's curve (same episodes), so a dominated setting cannot flatter the agent. **Negative = agent is below that frontier, i.e. better.** Mean ± std across runs, with the number of runs below. A `*` means at least one run's risk lay outside the family's range and was compared with its nearest setting. `best classical` uses, at each risk, the cheapest of all families; `best schedule` the cheapest excluding the spread-aware ones.

| urgency | AC, time clock | AC, volume clock (expected volume) | AC, volume clock (live volume) | POV | AC live, spread-aware k=0.5 | AC live, spread-aware k=1 | AC live, spread-aware k=2 | best schedule | best classical |
|---|---|---|---|---|---|---|---|---|---|
| 0 | +1.53 ± 3.71 (3/12)* | +1.45 ± 3.70 (3/12)* | +1.57 ± 3.70 (2/12)* | -2.40 ± 2.51 (11/12)* | +1.67 ± 3.70 (2/12)* | +1.71 ± 3.70 (2/12)* | +1.64 ± 3.69 (2/12)* | +1.57 ± 3.70 (2/12) | +1.71 ± 3.70 (2/12) |
| 0.25 | +0.18 ± 1.39 (9/12)* | +0.16 ± 1.36 (9/12)* | +0.34 ± 1.34 (6/12)* | -2.01 ± 0.83 (12/12)* | +0.44 ± 1.34 (6/12)* | +0.47 ± 1.34 (4/12)* | +0.42 ± 1.32 (6/12)* | +0.34 ± 1.34 (6/12) | +0.47 ± 1.34 (4/12) |
| 0.5 | -0.38 ± 0.38 (11/12) | -0.30 ± 0.33 (11/12) | -0.06 ± 0.33 (9/12) | -0.89 ± 0.40 (12/12) | +0.03 ± 0.33 (7/12) | +0.06 ± 0.33 (7/12)* | +0.00 ± 0.32 (7/12)* | -0.06 ± 0.33 (9/12) | +0.06 ± 0.33 (7/12) |
| 0.75 | -0.53 ± 0.19 (12/12) | -0.37 ± 0.16 (12/12) | -0.08 ± 0.15 (9/12) | -0.54 ± 0.24 (12/12) | -0.01 ± 0.15 (5/12) | +0.01 ± 0.14 (4/12) | -0.06 ± 0.15 (7/12) | -0.08 ± 0.15 (9/12) | +0.01 ± 0.14 (4/12) |
| 1 | -0.49 ± 0.17 (12/12) | -0.30 ± 0.17 (11/12) | +0.02 ± 0.14 (3/12) | -0.52 ± 0.19 (12/12) | +0.06 ± 0.14 (3/12) | +0.08 ± 0.14 (3/12) | +0.00 ± 0.13 (5/12) | +0.02 ± 0.14 (3/12) | +0.08 ± 0.14 (3/12) |

### Is the best-classical gap more than sampling noise?

95% interval for the `best classical` gap (averaged over runs), from 1000 bootstrap draws that resample whole ticker-days and re-score every strategy, rebuild every hull and recompute every gap on the same draw. The ± in the table above is only the spread across training seeds; this is the uncertainty from which days happened to be sampled.

| urgency | compared with | gap (bps) | 95% interval | excludes 0 |
|---|---|---|---|---|
| 0 | best schedule | +1.57 | [+1.21, +2.06] | yes |
| 0 | best classical incl. spread-aware | +1.71 | [+1.34, +2.18] | yes |
| 0.25 | best schedule | +0.34 | [+0.15, +0.58] | yes |
| 0.25 | best classical incl. spread-aware | +0.47 | [+0.28, +0.71] | yes |
| 0.5 | best schedule | -0.06 | [-0.17, +0.07] | NO |
| 0.5 | best classical incl. spread-aware | +0.06 | [-0.05, +0.19] | NO |
| 0.75 | best schedule | -0.08 | [-0.16, +0.00] | NO |
| 0.75 | best classical incl. spread-aware | +0.01 | [-0.07, +0.10] | NO |
| 1 | best schedule | +0.02 | [-0.06, +0.10] | NO |
| 1 | best classical incl. spread-aware | +0.08 | [-0.01, +0.17] | NO |

POV 5% and 7.5% may be off the top of the plot (it cannot finish orders of 5% ADV cleanly). See `frontier_urgency.png`.
