# RL urgency frontier vs Almgren-Chriss

Run configuration: `overrides: market.permanent_impact_mode=cumulative, market.impact_volume_ref=bar, reward_weights.disable_alpha_signal=true, execution.enable_passive=false, execution.action_squash=sigmoid, execution.drop_noise_obs=true, market.spread_impact_exp=0, market.vol_impact_exp=0`

Pairing with the benchmark episodes: PASS. Signed implementation shortfall. Risk = std of per-episode cost within side, averaged over sides.

## Pooled over all folds and runs

| strategy | risk (bps) | mean cost (bps) | finish step | done by 25% |
|---|---|---|---|---|
| RL urgency 0 | 124.4 | 8.25 | 386 | 36% |
| RL urgency 0.25 | 116.7 | 8.19 | 369 | 46% |
| RL urgency 0.5 | 109.6 | 8.34 | 341 | 57% |
| RL urgency 0.75 | 104.0 | 8.57 | 306 | 66% |
| RL urgency 1 | 100.3 | 8.80 | 265 | 74% |
| twap | 132.6 | 8.30 | 390 | 25% |
| vwap | 127.1 | 8.38 | 390 | 32% |
| ac@0.01 | 131.6 | 8.29 | 390 | 26% |
| ac@0.05 | 128.4 | 8.29 | 390 | 31% |
| ac@0.2 | 120.5 | 8.37 | 390 | 44% |
| ac@0.3 | 117.3 | 8.44 | 389 | 49% |
| ac@0.6 | 111.7 | 8.61 | 388 | 60% |
| ac@1 | 107.9 | 8.77 | 385 | 67% |
| ac@1.5 | 105.1 | 8.90 | 377 | 73% |
| ac@2.5 | 102.2 | 9.07 | 343 | 79% |
| ac@5 | 99.1 | 9.29 | 264 | 85% |
| ac@10 | 96.9 | 9.47 | 203 | 90% |
| ac@20 | 95.6 | 9.61 | 162 | 92% |
| acv@0.01 | 126.0 | 8.38 | 390 | 34% |
| acv@0.2 | 113.2 | 8.52 | 390 | 53% |
| acv@0.6 | 104.4 | 8.81 | 390 | 68% |
| acv@1.5 | 99.3 | 9.12 | 390 | 79% |
| acv@5 | 96.0 | 9.46 | 308 | 88% |
| acv@20 | 94.9 | 9.71 | 171 | 92% |
| acl@0.01 | 124.3 | 8.32 | 390 | 36% |
| acl@0.05 | 120.9 | 8.31 | 390 | 41% |
| acl@0.2 | 113.5 | 8.37 | 390 | 51% |
| acl@0.6 | 104.4 | 8.65 | 389 | 66% |
| acl@1 | 99.9 | 8.90 | 384 | 73% |
| acl@1.5 | 97.5 | 9.09 | 376 | 78% |
| acl@2.5 | 95.9 | 9.29 | 357 | 83% |
| acl@5 | 95.0 | 9.48 | 309 | 88% |
| acl@10 | 94.7 | 9.62 | 251 | 91% |
| acl@20 | 94.5 | 9.72 | 199 | 92% |
| pov@5 | 132.0 | 13.01 | 371 | 28% |
| pov@7.5 | 122.4 | 9.73 | 320 | 42% |
| pov@10 | 114.7 | 8.79 | 258 | 54% |
| pov@12.5 | 109.4 | 8.74 | 207 | 65% |
| pov@15 | 105.0 | 8.93 | 166 | 75% |
| pov@17.5 | 101.5 | 9.18 | 135 | 82% |
| pov@20 | 98.8 | 9.44 | 113 | 87% |
| pov@22.5 | 96.5 | 9.70 | 96 | 91% |
| pov@25 | 94.5 | 9.95 | 84 | 94% |

## Agent vs each benchmark family at equal risk, per run

Agent mean cost minus the family's mean cost at the same risk, interpolated along the lower convex hull of that fold's curve (same episodes), so a dominated setting cannot flatter the agent. **Negative = agent is below that frontier, i.e. better.** Mean ± std across runs, with the number of runs below. A `*` means at least one run's risk lay outside the family's range and was compared with its nearest setting. `best classical` uses, at each risk, the cheapest of all families.

| urgency | AC, time clock | AC, volume clock (expected volume) | AC, volume clock (live volume) | POV | best classical |
|---|---|---|---|---|---|
| 0 | -0.08 ± 0.24 (2/3) | -0.14 ± 0.24 (2/3)* | -0.07 ± 0.24 (2/3)* | -2.20 ± 0.74 (3/3) | -0.06 ± 0.24 (2/3) |
| 0.25 | -0.27 ± 0.11 (3/3) | -0.29 ± 0.11 (3/3) | -0.15 ± 0.11 (3/3) | -0.85 ± 0.26 (3/3) | -0.15 ± 0.11 (3/3) |
| 0.5 | -0.35 ± 0.05 (3/3) | -0.29 ± 0.06 (3/3) | -0.14 ± 0.06 (3/3) | -0.41 ± 0.06 (3/3) | -0.14 ± 0.06 (3/3) |
| 0.75 | -0.40 ± 0.05 (3/3) | -0.27 ± 0.05 (3/3) | -0.11 ± 0.05 (3/3) | -0.43 ± 0.05 (3/3) | -0.11 ± 0.05 (3/3) |
| 1 | -0.40 ± 0.04 (3/3) | -0.25 ± 0.04 (3/3) | -0.08 ± 0.04 (3/3) | -0.48 ± 0.06 (3/3) | -0.08 ± 0.04 (3/3) |

### Is the best-classical gap more than sampling noise?

95% interval for the `best classical` gap (averaged over runs), from 1000 bootstrap draws that resample whole ticker-days and re-score every strategy, rebuild every hull and recompute every gap on the same draw. The ± in the table above is only the spread across training seeds; this is the uncertainty from which days happened to be sampled.

| urgency | gap vs best classical (bps) | 95% interval | excludes 0 |
|---|---|---|---|
| 0 | -0.06 | [-0.17, +0.09] | NO |
| 0.25 | -0.15 | [-0.25, -0.05] | yes |
| 0.5 | -0.14 | [-0.26, -0.03] | yes |
| 0.75 | -0.11 | [-0.23, +0.01] | NO |
| 1 | -0.08 | [-0.20, +0.03] | NO |

POV 5% and 7.5% may be off the top of the plot (it cannot finish orders of 5% ADV cleanly). See `frontier_urgency.png`.
