# RL urgency frontier vs Almgren-Chriss

Run configuration: `overrides: market.vol_source=model`

Pairing with the benchmark episodes: PASS. Signed implementation shortfall. Risk = std of per-episode cost within side, averaged over sides.

## Pooled over all folds and runs

| strategy | risk (bps) | mean cost (bps) | finish step | done by 25% |
|---|---|---|---|---|
| RL urgency 0 | 114.0 | 9.16 | 364 | 41% |
| RL urgency 0.5 | 105.2 | 9.35 | 293 | 59% |
| RL urgency 1 | 98.5 | 9.76 | 204 | 75% |
| twap | 120.7 | 9.09 | 390 | 25% |
| vwap | 115.8 | 9.42 | 390 | 32% |
| ac@0.01 | 114.8 | 9.23 | 390 | 35% |
| ac@0.05 | 104.9 | 9.69 | 389 | 54% |
| ac@0.2 | 96.5 | 10.32 | 372 | 74% |
| ac@0.3 | 94.6 | 10.51 | 342 | 78% |
| ac@0.6 | 92.1 | 10.80 | 266 | 84% |
| ac@1 | 90.6 | 10.98 | 221 | 87% |
| ac@1.5 | 89.8 | 11.11 | 193 | 89% |
| ac@2.5 | 89.0 | 11.24 | 165 | 90% |
| ac@5 | 88.4 | 11.37 | 139 | 91% |
| ac@10 | 88.0 | 11.46 | 122 | 92% |
| ac@20 | 87.8 | 11.51 | 111 | 92% |
| acv@0.01 | 108.8 | 9.61 | 390 | 43% |
| acv@0.2 | 91.5 | 10.80 | 389 | 79% |
| acv@0.6 | 89.1 | 11.17 | 312 | 86% |
| acv@1.5 | 88.3 | 11.34 | 213 | 89% |
| acv@5 | 87.9 | 11.46 | 144 | 91% |
| acv@20 | 87.8 | 11.53 | 112 | 92% |
| acl@0.01 | 107.8 | 9.60 | 390 | 44% |
| acl@0.05 | 98.2 | 10.09 | 388 | 60% |
| acl@0.2 | 89.7 | 10.92 | 367 | 78% |
| acl@0.6 | 88.2 | 11.23 | 309 | 86% |
| acl@1 | 87.9 | 11.32 | 270 | 88% |
| acl@1.5 | 87.9 | 11.38 | 239 | 90% |
| acl@2.5 | 87.8 | 11.43 | 203 | 90% |
| acl@5 | 87.7 | 11.48 | 165 | 91% |
| acl@10 | 87.7 | 11.52 | 138 | 92% |
| acl@20 | 87.7 | 11.55 | 121 | 92% |
| pov@5 | 122.0 | 16.29 | 367 | 28% |
| pov@7.5 | 111.8 | 12.32 | 321 | 41% |
| pov@10 | 104.9 | 10.68 | 265 | 53% |
| pov@12.5 | 100.3 | 10.28 | 215 | 64% |
| pov@15 | 96.9 | 10.42 | 175 | 72% |
| pov@17.5 | 93.9 | 10.68 | 145 | 79% |
| pov@20 | 91.5 | 10.98 | 122 | 85% |
| pov@22.5 | 89.4 | 11.30 | 105 | 89% |
| pov@25 | 87.7 | 11.61 | 91 | 92% |
| acs0.5@0.01 | 103.4 | 9.60 | 389 | 53% |
| acs0.5@0.05 | 94.6 | 10.25 | 381 | 69% |
| acs0.5@0.2 | 88.9 | 11.01 | 340 | 83% |
| acs0.5@0.6 | 88.0 | 11.28 | 268 | 88% |
| acs0.5@1.5 | 87.8 | 11.41 | 204 | 90% |
| acs0.5@5 | 87.7 | 11.50 | 145 | 91% |
| acs0.5@20 | 87.7 | 11.56 | 112 | 92% |
| acs1@0.01 | 99.7 | 9.83 | 380 | 62% |
| acs1@0.05 | 92.9 | 10.44 | 355 | 74% |
| acs1@0.2 | 88.8 | 11.07 | 298 | 85% |
| acs1@0.6 | 88.0 | 11.30 | 230 | 89% |
| acs1@1.5 | 87.8 | 11.42 | 177 | 91% |
| acs1@5 | 87.7 | 11.51 | 131 | 92% |
| acs1@20 | 87.7 | 11.56 | 106 | 92% |
| acs2@0.01 | 96.1 | 10.17 | 317 | 71% |
| acs2@0.05 | 91.9 | 10.63 | 284 | 79% |
| acs2@0.2 | 88.9 | 11.13 | 231 | 86% |
| acs2@0.6 | 88.2 | 11.30 | 183 | 89% |
| acs2@1.5 | 87.9 | 11.40 | 147 | 91% |
| acs2@5 | 87.7 | 11.49 | 118 | 91% |
| acs2@20 | 87.7 | 11.55 | 102 | 92% |

## Agent vs each benchmark family at equal risk, per run

Agent mean cost minus the family's mean cost at the same risk, interpolated along the lower convex hull of that fold's curve (same episodes), so a dominated setting cannot flatter the agent. **Negative = agent is below that frontier, i.e. better.** Mean ± std across runs, with the number of runs below. A `*` means at least one run's risk lay outside the family's range and was compared with its nearest setting. `best classical` uses, at each risk, the cheapest of all families; `best schedule` the cheapest excluding the spread-aware ones.

| urgency | AC, time clock | AC, volume clock (expected volume) | AC, volume clock (live volume) | POV | AC live, spread-aware k=0.5 | AC live, spread-aware k=1 | AC live, spread-aware k=2 | best schedule | best classical |
|---|---|---|---|---|---|---|---|---|---|
| 0 | -0.15 ± 0.14 (9/12)* | -0.45 ± 0.16 (12/12)* | -0.44 ± 0.24 (12/12)* | -3.69 ± 1.55 (12/12)* | -0.45 ± 0.20 (12/12)* | -0.67 ± 0.23 (12/12)* | -1.01 ± 0.29 (12/12)* | -0.14 ± 0.14 (9/12) | -0.14 ± 0.14 (9/12) |
| 0.5 | -0.34 ± 0.08 (12/12) | -0.51 ± 0.15 (12/12)* | -0.38 ± 0.29 (9/12)* | -1.43 ± 0.56 (12/12) | -0.25 ± 0.18 (12/12)* | -0.47 ± 0.20 (12/12)* | -0.81 ± 0.26 (12/12)* | -0.25 ± 0.18 (9/12) | -0.21 ± 0.18 (9/12) |
| 1 | -0.42 ± 0.12 (12/12) | -0.55 ± 0.23 (12/12) | -0.33 ± 0.37 (9/12) | -0.62 ± 0.31 (12/12) | -0.20 ± 0.23 (9/12) | -0.20 ± 0.18 (11/12)* | -0.42 ± 0.28 (12/12)* | -0.27 ± 0.30 (9/12) | -0.14 ± 0.24 (9/12) |

### Is the best-classical gap more than sampling noise?

95% interval for the `best classical` gap (averaged over runs), from 1000 bootstrap draws that resample whole ticker-days and re-score every strategy, rebuild every hull and recompute every gap on the same draw. The ± in the table above is only the spread across training seeds; this is the uncertainty from which days happened to be sampled.

| urgency | compared with | gap (bps) | 95% interval | excludes 0 |
|---|---|---|---|---|
| 0 | best schedule | -0.14 | [-0.24, -0.04] | yes |
| 0 | best classical incl. spread-aware | -0.14 | [-0.24, -0.04] | yes |
| 0.5 | best schedule | -0.25 | [-0.39, -0.13] | yes |
| 0.5 | best classical incl. spread-aware | -0.21 | [-0.32, -0.10] | yes |
| 1 | best schedule | -0.27 | [-0.44, -0.12] | yes |
| 1 | best classical incl. spread-aware | -0.14 | [-0.28, -0.00] | yes |

POV 5% and 7.5% may be off the top of the plot (it cannot finish orders of 5% ADV cleanly). See `frontier_urgency.png`.
