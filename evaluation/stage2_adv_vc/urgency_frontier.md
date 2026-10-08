# RL urgency frontier vs Almgren-Chriss

Run configuration: `overrides: market.permanent_impact_mode=cumulative, market.impact_volume_ref=bar, reward_weights.disable_alpha_signal=true, execution.enable_passive=false, execution.action_squash=sigmoid, execution.drop_noise_obs=true, execution.action_mode=adv_rate`

Pairing with the benchmark episodes: PASS. Signed implementation shortfall. Risk = std of per-episode cost within side, averaged over sides.

## Pooled over all folds and runs

| strategy | risk (bps) | mean cost (bps) | finish step | done by 25% |
|---|---|---|---|---|
| RL urgency 0 | 119.5 | 9.27 | 359 | 44% |
| RL urgency 0.25 | 114.8 | 9.21 | 348 | 51% |
| RL urgency 0.5 | 109.3 | 9.35 | 328 | 59% |
| RL urgency 0.75 | 104.5 | 9.60 | 296 | 68% |
| RL urgency 1 | 101.1 | 9.89 | 247 | 75% |
| twap | 132.6 | 8.86 | 390 | 25% |
| vwap | 127.1 | 8.94 | 390 | 32% |
| ac@0.01 | 131.6 | 8.85 | 390 | 26% |
| ac@0.05 | 128.4 | 8.86 | 390 | 31% |
| ac@0.2 | 120.5 | 8.99 | 390 | 44% |
| ac@0.3 | 117.3 | 9.10 | 389 | 49% |
| ac@0.6 | 111.7 | 9.35 | 388 | 60% |
| ac@1 | 107.9 | 9.58 | 385 | 67% |
| ac@1.5 | 105.2 | 9.77 | 377 | 73% |
| ac@2.5 | 102.2 | 10.01 | 343 | 79% |
| ac@5 | 99.1 | 10.31 | 264 | 85% |
| ac@10 | 96.9 | 10.57 | 203 | 90% |
| ac@20 | 95.6 | 10.78 | 162 | 92% |
| acv@0.01 | 126.0 | 8.94 | 390 | 34% |
| acv@0.2 | 113.2 | 9.19 | 390 | 53% |
| acv@0.6 | 104.4 | 9.63 | 390 | 68% |
| acv@1.5 | 99.3 | 10.08 | 390 | 79% |
| acv@5 | 96.0 | 10.57 | 308 | 88% |
| acv@20 | 94.9 | 10.91 | 171 | 92% |
| acl@0.01 | 124.3 | 8.88 | 390 | 36% |
| acl@0.05 | 120.9 | 8.87 | 390 | 41% |
| acl@0.2 | 113.5 | 8.98 | 390 | 51% |
| acl@0.6 | 104.5 | 9.40 | 389 | 66% |
| acl@1 | 100.0 | 9.77 | 384 | 73% |
| acl@1.5 | 97.6 | 10.04 | 376 | 78% |
| acl@2.5 | 96.0 | 10.31 | 357 | 83% |
| acl@5 | 95.1 | 10.59 | 309 | 88% |
| acl@10 | 94.7 | 10.79 | 251 | 91% |
| acl@20 | 94.6 | 10.93 | 199 | 92% |
| pov@5 | 132.4 | 15.02 | 371 | 28% |
| pov@7.5 | 122.5 | 10.79 | 320 | 42% |
| pov@10 | 114.7 | 9.58 | 258 | 54% |
| pov@12.5 | 109.4 | 9.53 | 207 | 65% |
| pov@15 | 105.1 | 9.81 | 166 | 75% |
| pov@17.5 | 101.5 | 10.17 | 136 | 82% |
| pov@20 | 98.8 | 10.54 | 113 | 87% |
| pov@22.5 | 96.5 | 10.90 | 97 | 91% |
| pov@25 | 94.6 | 11.25 | 84 | 94% |

## Agent vs each benchmark family at equal risk, per run

Agent mean cost minus the family's mean cost at the same risk, interpolated along the lower convex hull of that fold's curve (same episodes), so a dominated setting cannot flatter the agent. **Negative = agent is below that frontier, i.e. better.** Mean ± std across runs, with the number of runs below. A `*` means at least one run's risk lay outside the family's range and was compared with its nearest setting. `best classical` uses, at each risk, the cheapest of all families.

| urgency | AC, time clock | AC, volume clock (expected volume) | AC, volume clock (live volume) | POV | best classical |
|---|---|---|---|---|---|
| 0 | +0.18 ± 0.16 (0/3) | +0.18 ± 0.11 (0/3)* | +0.32 ± 0.14 (0/3)* | -1.69 ± 2.11 (3/3) | +0.33 ± 0.13 (0/3) |
| 0.25 | -0.05 ± 0.09 (2/3) | -0.00 ± 0.04 (1/3) | +0.18 ± 0.06 (0/3) | -0.78 ± 0.86 (3/3) | +0.18 ± 0.06 (0/3) |
| 0.5 | -0.17 ± 0.09 (3/3) | -0.05 ± 0.10 (2/3) | +0.16 ± 0.10 (0/3) | -0.32 ± 0.09 (3/3) | +0.16 ± 0.10 (0/3) |
| 0.75 | -0.24 ± 0.05 (3/3) | -0.07 ± 0.07 (3/3) | +0.16 ± 0.08 (0/3) | -0.30 ± 0.05 (3/3) | +0.16 ± 0.08 (0/3) |
| 1 | -0.23 ± 0.06 (3/3) | -0.03 ± 0.06 (2/3) | +0.21 ± 0.07 (0/3) | -0.35 ± 0.01 (3/3) | +0.21 ± 0.07 (0/3) |

POV 5% and 7.5% may be off the top of the plot (it cannot finish orders of 5% ADV cleanly). See `frontier_urgency.png`.
