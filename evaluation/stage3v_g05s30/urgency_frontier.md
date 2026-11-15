# RL urgency frontier vs Almgren-Chriss

Run configuration: `overrides: none`

Pairing with the benchmark episodes: PASS. Signed implementation shortfall. Risk = std of per-episode cost within side, averaged over sides.

## Pooled over all folds and runs

| strategy | risk (bps) | mean cost (bps) | finish step | done by 25% |
|---|---|---|---|---|
| RL urgency 0 | 120.2 | 9.77 | 379 | 32% |
| RL urgency 0.25 | 109.5 | 9.75 | 306 | 51% |
| RL urgency 0.5 | 100.7 | 10.11 | 206 | 70% |
| RL urgency 0.75 | 95.2 | 10.68 | 144 | 82% |
| RL urgency 1 | 92.2 | 11.15 | 117 | 87% |
| twap | 122.4 | 9.27 | 390 | 25% |
| vwap | 117.7 | 9.68 | 390 | 32% |
| ac@0.01 | 116.6 | 9.46 | 390 | 35% |
| ac@0.05 | 106.6 | 10.04 | 389 | 54% |
| ac@0.2 | 98.0 | 10.84 | 372 | 74% |
| ac@0.3 | 96.0 | 11.07 | 342 | 78% |
| ac@0.6 | 93.4 | 11.42 | 267 | 84% |
| ac@1 | 91.9 | 11.64 | 221 | 87% |
| ac@1.5 | 91.0 | 11.79 | 193 | 89% |
| ac@2.5 | 90.2 | 11.94 | 166 | 90% |
| ac@5 | 89.6 | 12.10 | 140 | 91% |
| ac@10 | 89.2 | 12.20 | 123 | 91% |
| ac@20 | 89.0 | 12.27 | 112 | 92% |
| acv@0.01 | 110.7 | 9.93 | 390 | 43% |
| acv@0.2 | 93.0 | 11.39 | 389 | 79% |
| acv@0.6 | 90.4 | 11.83 | 312 | 86% |
| acv@1.5 | 89.5 | 12.05 | 214 | 89% |
| acv@5 | 89.1 | 12.21 | 145 | 91% |
| acv@20 | 88.9 | 12.30 | 113 | 92% |
| acl@0.01 | 108.9 | 9.92 | 390 | 44% |
| acl@0.05 | 99.2 | 10.51 | 388 | 60% |
| acl@0.2 | 90.8 | 11.55 | 368 | 78% |
| acl@0.6 | 89.3 | 11.94 | 308 | 86% |
| acl@1 | 89.1 | 12.05 | 269 | 88% |
| acl@1.5 | 89.0 | 12.11 | 239 | 89% |
| acl@2.5 | 88.9 | 12.17 | 205 | 90% |
| acl@5 | 88.9 | 12.24 | 167 | 91% |
| acl@10 | 88.9 | 12.28 | 140 | 91% |
| acl@20 | 88.9 | 12.31 | 122 | 92% |
| pov@5 | 123.3 | 17.13 | 368 | 28% |
| pov@7.5 | 112.3 | 12.81 | 320 | 41% |
| pov@10 | 105.4 | 11.09 | 264 | 53% |
| pov@12.5 | 100.9 | 10.71 | 216 | 63% |
| pov@15 | 97.6 | 10.91 | 177 | 72% |
| pov@17.5 | 94.8 | 11.24 | 146 | 79% |
| pov@20 | 92.5 | 11.61 | 123 | 85% |
| pov@22.5 | 90.5 | 12.00 | 105 | 89% |
| pov@25 | 88.9 | 12.38 | 92 | 92% |
| acs0.5@0.01 | 104.5 | 9.98 | 388 | 53% |
| acs0.5@0.05 | 95.6 | 10.77 | 381 | 68% |
| acs0.5@0.2 | 90.0 | 11.67 | 340 | 82% |
| acs0.5@0.6 | 89.1 | 12.00 | 268 | 88% |
| acs0.5@1.5 | 89.0 | 12.15 | 206 | 90% |
| acs0.5@5 | 88.9 | 12.26 | 147 | 91% |
| acs0.5@20 | 88.9 | 12.32 | 113 | 92% |
| acs1@0.01 | 100.9 | 10.29 | 379 | 61% |
| acs1@0.05 | 93.9 | 11.01 | 355 | 74% |
| acs1@0.2 | 89.8 | 11.75 | 298 | 84% |
| acs1@0.6 | 89.1 | 12.03 | 232 | 89% |
| acs1@1.5 | 89.0 | 12.17 | 179 | 90% |
| acs1@5 | 88.9 | 12.27 | 133 | 91% |
| acs1@20 | 88.9 | 12.32 | 108 | 92% |
| acs2@0.01 | 97.3 | 10.73 | 318 | 70% |
| acs2@0.05 | 92.8 | 11.26 | 286 | 79% |
| acs2@0.2 | 89.9 | 11.82 | 235 | 86% |
| acs2@0.6 | 89.3 | 12.03 | 187 | 89% |
| acs2@1.5 | 89.1 | 12.15 | 151 | 90% |
| acs2@5 | 88.9 | 12.25 | 120 | 91% |
| acs2@20 | 88.9 | 12.31 | 104 | 92% |

## Agent vs each benchmark family at equal risk, per run

Agent mean cost minus the family's mean cost at the same risk, interpolated along the lower convex hull of that fold's curve (same episodes), so a dominated setting cannot flatter the agent. **Negative = agent is below that frontier, i.e. better.** Mean ± std across runs, with the number of runs below. A `*` means at least one run's risk lay outside the family's range and was compared with its nearest setting. `best classical` uses, at each risk, the cheapest of all families; `best schedule` the cheapest excluding the spread-aware ones.

| urgency | AC, time clock | AC, volume clock (expected volume) | AC, volume clock (live volume) | POV | AC live, spread-aware k=0.5 | AC live, spread-aware k=1 | AC live, spread-aware k=2 | best schedule | best classical |
|---|---|---|---|---|---|---|---|---|---|
| 0 | +0.30 ± 0.44 (3/12)* | -0.15 ± 0.38 (7/12)* | -0.15 ± 0.46 (8/12)* | -5.18 ± 2.65 (12/12)* | -0.21 ± 0.47 (9/12)* | -0.52 ± 0.49 (9/12)* | -0.96 ± 0.56 (12/12)* | +0.30 ± 0.44 (3/12) | +0.30 ± 0.44 (3/12) |
| 0.25 | -0.12 ± 0.51 (8/12) | -0.38 ± 0.44 (9/12)* | -0.24 ± 0.49 (8/12)* | -2.32 ± 1.20 (12/12)* | -0.23 ± 0.42 (9/12)* | -0.54 ± 0.47 (10/12)* | -0.98 ± 0.57 (12/12)* | -0.04 ± 0.46 (7/12) | -0.04 ± 0.46 (7/12) |
| 0.5 | -0.44 ± 0.42 (9/12) | -0.60 ± 0.40 (11/12) | -0.33 ± 0.47 (8/12) | -0.77 ± 0.59 (11/12) | -0.20 ± 0.39 (8/12)* | -0.30 ± 0.38 (9/12)* | -0.64 ± 0.45 (12/12)* | -0.27 ± 0.42 (8/12) | -0.15 ± 0.38 (8/12) |
| 0.75 | -0.45 ± 0.18 (12/12) | -0.52 ± 0.24 (12/12) | -0.32 ± 0.33 (10/12) | -0.54 ± 0.33 (12/12) | -0.19 ± 0.25 (9/12) | -0.21 ± 0.21 (10/12) | -0.32 ± 0.26 (11/12)* | -0.28 ± 0.29 (10/12) | -0.15 ± 0.25 (8/12) |
| 1 | -0.40 ± 0.29 (12/12) | -0.39 ± 0.31 (12/12) | -0.23 ± 0.37 (8/12) | -0.53 ± 0.28 (12/12) | -0.18 ± 0.32 (7/12) | -0.19 ± 0.31 (7/12) | -0.25 ± 0.29 (10/12)* | -0.21 ± 0.37 (8/12) | -0.14 ± 0.35 (7/12) |

### Is the best-classical gap more than sampling noise?

95% interval for the `best classical` gap (averaged over runs), from 1000 bootstrap draws that resample whole ticker-days and re-score every strategy, rebuild every hull and recompute every gap on the same draw. The ± in the table above is only the spread across training seeds; this is the uncertainty from which days happened to be sampled.

| urgency | compared with | gap (bps) | 95% interval | excludes 0 |
|---|---|---|---|---|
| 0 | best schedule | +0.30 | [+0.18, +0.42] | yes |
| 0 | best classical incl. spread-aware | +0.30 | [+0.18, +0.42] | yes |
| 0.25 | best schedule | -0.04 | [-0.17, +0.08] | NO |
| 0.25 | best classical incl. spread-aware | -0.04 | [-0.16, +0.09] | NO |
| 0.5 | best schedule | -0.27 | [-0.41, -0.12] | yes |
| 0.5 | best classical incl. spread-aware | -0.15 | [-0.32, -0.02] | yes |
| 0.75 | best schedule | -0.28 | [-0.42, -0.09] | yes |
| 0.75 | best classical incl. spread-aware | -0.15 | [-0.33, +0.03] | NO |
| 1 | best schedule | -0.21 | [-0.36, -0.04] | yes |
| 1 | best classical incl. spread-aware | -0.14 | [-0.30, +0.05] | NO |

POV 5% and 7.5% may be off the top of the plot (it cannot finish orders of 5% ADV cleanly). See `frontier_urgency.png`.
