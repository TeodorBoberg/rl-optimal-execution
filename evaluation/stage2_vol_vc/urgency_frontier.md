# RL urgency frontier vs Almgren-Chriss

Run configuration: `overrides: market.permanent_impact_mode=cumulative, market.impact_volume_ref=bar, reward_weights.disable_alpha_signal=true, execution.enable_passive=false, execution.action_squash=sigmoid, execution.drop_noise_obs=true`

Pairing with the benchmark episodes: PASS. Signed implementation shortfall. Risk = std of per-episode cost within side, averaged over sides.

## Pooled over all folds and runs

| strategy | risk (bps) | mean cost (bps) | finish step | done by 25% |
|---|---|---|---|---|
| RL urgency 0 | 124.4 | 8.77 | 386 | 36% |
| RL urgency 0.25 | 116.7 | 8.66 | 369 | 46% |
| RL urgency 0.5 | 109.6 | 8.89 | 341 | 57% |
| RL urgency 0.75 | 104.0 | 9.23 | 306 | 66% |
| RL urgency 1 | 100.3 | 9.59 | 265 | 74% |
| twap | 132.6 | 8.85 | 390 | 25% |
| vwap | 127.1 | 8.95 | 390 | 32% |
| ac@0.01 | 131.6 | 8.84 | 390 | 26% |
| ac@0.05 | 128.4 | 8.85 | 390 | 31% |
| ac@0.2 | 120.5 | 8.99 | 390 | 44% |
| ac@0.3 | 117.3 | 9.10 | 389 | 49% |
| ac@0.6 | 111.7 | 9.35 | 388 | 60% |
| ac@1 | 107.9 | 9.58 | 385 | 67% |
| ac@1.5 | 105.2 | 9.77 | 377 | 73% |
| ac@2.5 | 102.2 | 10.01 | 343 | 79% |
| ac@5 | 99.1 | 10.31 | 264 | 85% |
| ac@10 | 96.9 | 10.57 | 203 | 90% |
| ac@20 | 95.6 | 10.78 | 162 | 92% |
| acv@0.01 | 126.0 | 8.95 | 390 | 34% |
| acv@0.2 | 113.2 | 9.19 | 390 | 53% |
| acv@0.6 | 104.4 | 9.63 | 390 | 68% |
| acv@1.5 | 99.3 | 10.07 | 390 | 79% |
| acv@5 | 96.0 | 10.57 | 308 | 88% |
| acv@20 | 94.9 | 10.92 | 171 | 92% |
| acl@0.01 | 124.3 | 8.90 | 390 | 36% |
| acl@0.05 | 120.9 | 8.88 | 390 | 41% |
| acl@0.2 | 113.5 | 8.99 | 390 | 51% |
| acl@0.6 | 104.4 | 9.41 | 389 | 66% |
| acl@1 | 99.9 | 9.78 | 384 | 73% |
| acl@1.5 | 97.5 | 10.05 | 376 | 78% |
| acl@2.5 | 95.9 | 10.33 | 357 | 83% |
| acl@5 | 95.0 | 10.62 | 309 | 88% |
| acl@10 | 94.7 | 10.81 | 251 | 91% |
| acl@20 | 94.5 | 10.95 | 199 | 92% |
| pov@5 | 132.4 | 15.02 | 371 | 28% |
| pov@7.5 | 122.5 | 10.79 | 320 | 42% |
| pov@10 | 114.7 | 9.58 | 258 | 54% |
| pov@12.5 | 109.4 | 9.53 | 207 | 65% |
| pov@15 | 105.1 | 9.81 | 166 | 75% |
| pov@17.5 | 101.5 | 10.18 | 135 | 82% |
| pov@20 | 98.8 | 10.55 | 113 | 87% |
| pov@22.5 | 96.5 | 10.92 | 96 | 91% |
| pov@25 | 94.5 | 11.27 | 84 | 94% |

## Agent vs each benchmark family at equal risk, per run

Agent mean cost minus the family's mean cost at the same risk, interpolated along the lower convex hull of that fold's curve (same episodes), so a dominated setting cannot flatter the agent. **Negative = agent is below that frontier, i.e. better.** Mean ± std across runs, with the number of runs below. A `*` means at least one run's risk lay outside the family's range and was compared with its nearest setting. `best classical` uses, at each risk, the cheapest of all families.

| urgency | AC, time clock | AC, volume clock (expected volume) | AC, volume clock (live volume) | POV | best classical |
|---|---|---|---|---|---|
| 0 | -0.15 ± 0.26 (2/3) | -0.21 ± 0.26 (2/3)* | -0.12 ± 0.26 (2/3)* | -2.89 ± 0.95 (3/3) | -0.12 ± 0.26 (2/3) |
| 0.25 | -0.46 ± 0.11 (3/3) | -0.46 ± 0.12 (3/3) | -0.28 ± 0.12 (3/3) | -1.24 ± 0.33 (3/3) | -0.28 ± 0.12 (3/3) |
| 0.5 | -0.58 ± 0.05 (3/3) | -0.48 ± 0.06 (3/3) | -0.28 ± 0.06 (3/3) | -0.67 ± 0.06 (3/3) | -0.28 ± 0.06 (3/3) |
| 0.75 | -0.63 ± 0.06 (3/3) | -0.43 ± 0.06 (3/3) | -0.21 ± 0.06 (3/3) | -0.68 ± 0.06 (3/3) | -0.21 ± 0.06 (3/3) |
| 1 | -0.60 ± 0.05 (3/3) | -0.39 ± 0.05 (3/3) | -0.16 ± 0.06 (3/3) | -0.74 ± 0.07 (3/3) | -0.16 ± 0.06 (3/3) |

### Is the best-classical gap more than sampling noise?

95% interval for the `best classical` gap (averaged over runs), from 1000 bootstrap draws that resample whole ticker-days and re-score every strategy, rebuild every hull and recompute every gap on the same draw. The ± in the table above is only the spread across training seeds; this is the uncertainty from which days happened to be sampled.

| urgency | gap vs best classical (bps) | 95% interval | excludes 0 |
|---|---|---|---|
| 0 | -0.12 | [-0.25, +0.07] | NO |
| 0.25 | -0.28 | [-0.38, -0.17] | yes |
| 0.5 | -0.28 | [-0.41, -0.15] | yes |
| 0.75 | -0.21 | [-0.37, -0.09] | yes |
| 1 | -0.16 | [-0.31, -0.02] | yes |

POV 5% and 7.5% may be off the top of the plot (it cannot finish orders of 5% ADV cleanly). See `frontier_urgency.png`.
