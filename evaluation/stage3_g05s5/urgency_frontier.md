# RL urgency frontier vs Almgren-Chriss

Run configuration: `overrides: none`

Pairing with the benchmark episodes: PASS. Signed implementation shortfall. Risk = std of per-episode cost within side, averaged over sides.

## Pooled over all folds and runs

| strategy | risk (bps) | mean cost (bps) | finish step | done by 25% |
|---|---|---|---|---|
| RL urgency 0 | 117.9 | 9.37 | 370 | 36% |
| RL urgency 0.25 | 108.1 | 9.52 | 304 | 53% |
| RL urgency 0.5 | 100.1 | 9.92 | 215 | 70% |
| RL urgency 0.75 | 95.1 | 10.56 | 149 | 82% |
| RL urgency 1 | 92.3 | 11.10 | 119 | 87% |
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
| 0 | -0.14 ± 0.39 (6/12)* | -0.58 ± 0.34 (12/12)* | -0.55 ± 0.38 (12/12)* | -4.85 ± 2.46 (12/12)* | -0.61 ± 0.37 (12/12)* | -0.92 ± 0.40 (12/12)* | -1.36 ± 0.48 (12/12)* | -0.12 ± 0.34 (6/12) | -0.12 ± 0.34 (6/12) |
| 0.25 | -0.44 ± 0.35 (12/12) | -0.62 ± 0.33 (12/12)* | -0.49 ± 0.38 (11/12)* | -2.16 ± 1.31 (12/12) | -0.48 ± 0.38 (12/12)* | -0.77 ± 0.41 (12/12)* | -1.21 ± 0.51 (12/12)* | -0.35 ± 0.32 (11/12) | -0.34 ± 0.33 (11/12) |
| 0.5 | -0.70 ± 0.20 (12/12) | -0.86 ± 0.27 (12/12) | -0.57 ± 0.40 (11/12) | -0.95 ± 0.58 (12/12) | -0.44 ± 0.28 (11/12) | -0.51 ± 0.24 (12/12)* | -0.82 ± 0.41 (12/12)* | -0.53 ± 0.37 (11/12) | -0.39 ± 0.30 (11/12) |
| 0.75 | -0.60 ± 0.19 (12/12) | -0.66 ± 0.23 (12/12) | -0.46 ± 0.36 (9/12) | -0.68 ± 0.33 (12/12) | -0.34 ± 0.29 (10/12) | -0.35 ± 0.25 (11/12) | -0.46 ± 0.22 (12/12)* | -0.42 ± 0.35 (9/12) | -0.31 ± 0.30 (9/12) |
| 1 | -0.46 ± 0.33 (11/12) | -0.41 ± 0.32 (11/12) | -0.26 ± 0.40 (8/12) | -0.58 ± 0.35 (12/12) | -0.20 ± 0.36 (7/12) | -0.22 ± 0.36 (7/12) | -0.29 ± 0.34 (8/12) | -0.25 ± 0.40 (8/12) | -0.18 ± 0.39 (7/12) |

### Is the best-classical gap more than sampling noise?

95% interval for the `best classical` gap (averaged over runs), from 1000 bootstrap draws that resample whole ticker-days and re-score every strategy, rebuild every hull and recompute every gap on the same draw. The ± in the table above is only the spread across training seeds; this is the uncertainty from which days happened to be sampled.

| urgency | compared with | gap (bps) | 95% interval | excludes 0 |
|---|---|---|---|---|
| 0 | best schedule | -0.12 | [-0.20, -0.05] | yes |
| 0 | best classical incl. spread-aware | -0.12 | [-0.20, -0.05] | yes |
| 0.25 | best schedule | -0.35 | [-0.46, -0.25] | yes |
| 0.25 | best classical incl. spread-aware | -0.34 | [-0.44, -0.23] | yes |
| 0.5 | best schedule | -0.53 | [-0.66, -0.37] | yes |
| 0.5 | best classical incl. spread-aware | -0.39 | [-0.54, -0.26] | yes |
| 0.75 | best schedule | -0.42 | [-0.57, -0.23] | yes |
| 0.75 | best classical incl. spread-aware | -0.31 | [-0.47, -0.12] | yes |
| 1 | best schedule | -0.25 | [-0.40, -0.07] | yes |
| 1 | best classical incl. spread-aware | -0.18 | [-0.34, +0.01] | NO |

POV 5% and 7.5% may be off the top of the plot (it cannot finish orders of 5% ADV cleanly). See `frontier_urgency.png`.
