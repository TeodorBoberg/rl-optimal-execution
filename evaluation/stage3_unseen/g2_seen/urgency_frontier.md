# RL urgency frontier vs Almgren-Chriss

Run configuration: `overrides: none`

Pairing with the benchmark episodes: PASS. Signed implementation shortfall. Risk = std of per-episode cost within side, averaged over sides.

## Pooled over all folds and runs

| strategy | risk (bps) | mean cost (bps) | finish step | done by 25% |
|---|---|---|---|---|
| RL urgency 0 | 145.2 | 10.99 | 377 | 31% |
| RL urgency 0.25 | 129.5 | 10.88 | 327 | 48% |
| RL urgency 0.5 | 117.3 | 11.09 | 236 | 66% |
| RL urgency 0.75 | 111.0 | 12.02 | 161 | 79% |
| RL urgency 1 | 107.6 | 12.84 | 126 | 85% |
| twap | 150.2 | 10.82 | 390 | 25% |
| vwap | 143.3 | 11.68 | 390 | 32% |
| ac@0.01 | 140.7 | 11.02 | 390 | 36% |
| ac@0.05 | 125.5 | 11.82 | 389 | 56% |
| ac@0.2 | 113.7 | 12.87 | 368 | 74% |
| ac@0.3 | 111.2 | 13.17 | 333 | 78% |
| ac@0.6 | 108.0 | 13.60 | 260 | 83% |
| ac@1 | 106.5 | 13.87 | 218 | 86% |
| ac@1.5 | 105.7 | 14.04 | 193 | 87% |
| ac@2.5 | 104.9 | 14.21 | 168 | 88% |
| ac@5 | 104.1 | 14.41 | 145 | 89% |
| ac@10 | 103.4 | 14.58 | 130 | 90% |
| ac@20 | 103.1 | 14.71 | 120 | 90% |
| acv@0.01 | 132.0 | 11.84 | 390 | 44% |
| acv@0.2 | 107.8 | 13.58 | 388 | 78% |
| acv@0.6 | 104.9 | 14.10 | 307 | 85% |
| acv@1.5 | 103.6 | 14.41 | 215 | 88% |
| acv@5 | 103.2 | 14.63 | 151 | 89% |
| acv@20 | 103.2 | 14.76 | 122 | 90% |
| acl@0.01 | 134.4 | 12.12 | 390 | 43% |
| acl@0.05 | 120.1 | 12.77 | 389 | 59% |
| acl@0.2 | 106.8 | 13.96 | 369 | 77% |
| acl@0.6 | 104.1 | 14.36 | 325 | 84% |
| acl@1 | 103.7 | 14.48 | 291 | 87% |
| acl@1.5 | 103.4 | 14.55 | 262 | 88% |
| acl@2.5 | 103.3 | 14.61 | 225 | 89% |
| acl@5 | 103.2 | 14.69 | 183 | 89% |
| acl@10 | 103.2 | 14.73 | 154 | 90% |
| acl@20 | 103.1 | 14.76 | 135 | 90% |
| pov@5 | 159.4 | 33.84 | 371 | 25% |
| pov@7.5 | 144.3 | 22.16 | 340 | 37% |
| pov@10 | 134.3 | 15.94 | 294 | 48% |
| pov@12.5 | 126.3 | 13.35 | 245 | 58% |
| pov@15 | 120.0 | 12.83 | 201 | 67% |
| pov@17.5 | 114.1 | 13.20 | 166 | 75% |
| pov@20 | 109.4 | 13.76 | 139 | 81% |
| pov@22.5 | 105.8 | 14.30 | 118 | 86% |
| pov@25 | 103.2 | 14.84 | 102 | 90% |
| acs0.5@0.01 | 125.8 | 11.98 | 388 | 54% |
| acs0.5@0.05 | 113.0 | 12.98 | 374 | 69% |
| acs0.5@0.2 | 104.8 | 14.09 | 339 | 81% |
| acs0.5@0.6 | 103.5 | 14.43 | 284 | 87% |
| acs0.5@1.5 | 103.2 | 14.59 | 224 | 89% |
| acs0.5@5 | 103.1 | 14.71 | 161 | 90% |
| acs0.5@20 | 103.1 | 14.78 | 126 | 90% |
| acs1@0.01 | 118.7 | 12.25 | 370 | 64% |
| acs1@0.05 | 109.6 | 13.18 | 342 | 75% |
| acs1@0.2 | 104.1 | 14.15 | 300 | 84% |
| acs1@0.6 | 103.2 | 14.47 | 244 | 88% |
| acs1@1.5 | 103.1 | 14.62 | 194 | 89% |
| acs1@5 | 103.1 | 14.72 | 144 | 90% |
| acs1@20 | 103.1 | 14.78 | 119 | 90% |
| acs2@0.01 | 112.9 | 12.66 | 309 | 74% |
| acs2@0.05 | 107.2 | 13.40 | 285 | 81% |
| acs2@0.2 | 103.6 | 14.18 | 238 | 86% |
| acs2@0.6 | 103.2 | 14.47 | 190 | 88% |
| acs2@1.5 | 103.1 | 14.62 | 152 | 89% |
| acs2@5 | 103.1 | 14.71 | 126 | 90% |
| acs2@20 | 103.1 | 14.78 | 112 | 90% |

## Agent vs each benchmark family at equal risk, per run

Agent mean cost minus the family's mean cost at the same risk, interpolated along the lower convex hull of that fold's curve (same episodes), so a dominated setting cannot flatter the agent. **Negative = agent is below that frontier, i.e. better.** Mean ± std across runs, with the number of runs below. A `*` means at least one run's risk lay outside the family's range and was compared with its nearest setting. `best classical` uses, at each risk, the cheapest of all families; `best schedule` the cheapest excluding the spread-aware ones.

| urgency | AC, time clock | AC, volume clock (expected volume) | AC, volume clock (live volume) | POV | AC live, spread-aware k=0.5 | AC live, spread-aware k=1 | AC live, spread-aware k=2 | best schedule | best classical |
|---|---|---|---|---|---|---|---|---|---|
| 0 | -0.08 ± 0.46 (2/3)* | -0.86 ± 0.48 (3/3)* | -1.13 ± 0.48 (3/3)* | -12.22 ± 4.51 (3/3) | -1.00 ± 0.48 (3/3)* | -1.27 ± 0.48 (3/3)* | -1.67 ± 0.48 (3/3)* | -0.08 ± 0.46 (2/3) | -0.08 ± 0.46 (2/3) |
| 0.25 | -0.74 ± 0.25 (3/3) | -1.17 ± 0.26 (3/3)* | -1.46 ± 0.23 (3/3) | -3.65 ± 1.25 (3/3) | -1.13 ± 0.17 (3/3)* | -1.38 ± 0.19 (3/3)* | -1.78 ± 0.19 (3/3)* | -0.74 ± 0.25 (3/3) | -0.74 ± 0.25 (3/3) |
| 0.5 | -1.45 ± 0.23 (3/3) | -1.80 ± 0.21 (3/3) | -1.93 ± 0.23 (3/3) | -1.90 ± 0.20 (3/3) | -1.55 ± 0.21 (3/3) | -1.33 ± 0.20 (3/3)* | -1.56 ± 0.19 (3/3)* | -1.45 ± 0.23 (3/3) | -1.33 ± 0.20 (3/3) |
| 0.75 | -1.16 ± 0.27 (3/3) | -1.33 ± 0.29 (3/3) | -1.56 ± 0.28 (3/3) | -1.53 ± 0.28 (3/3) | -1.22 ± 0.27 (3/3) | -1.01 ± 0.28 (3/3) | -0.87 ± 0.28 (3/3) | -1.16 ± 0.27 (3/3) | -0.87 ± 0.28 (3/3) |
| 1 | -0.82 ± 0.30 (3/3) | -0.76 ± 0.29 (3/3) | -1.04 ± 0.30 (3/3) | -1.18 ± 0.30 (3/3) | -0.86 ± 0.30 (3/3) | -0.67 ± 0.30 (3/3) | -0.49 ± 0.30 (3/3) | -0.76 ± 0.29 (3/3) | -0.49 ± 0.30 (3/3) |

### Is the best-classical gap more than sampling noise?

95% interval for the `best classical` gap (averaged over runs), from 1000 bootstrap draws that resample whole ticker-days and re-score every strategy, rebuild every hull and recompute every gap on the same draw. The ± in the table above is only the spread across training seeds; this is the uncertainty from which days happened to be sampled.

| urgency | compared with | gap (bps) | 95% interval | excludes 0 |
|---|---|---|---|---|
| 0 | best schedule | -0.08 | [-0.39, +0.24] | NO |
| 0 | best classical incl. spread-aware | -0.08 | [-0.39, +0.24] | NO |
| 0.25 | best schedule | -0.74 | [-1.09, -0.42] | yes |
| 0.25 | best classical incl. spread-aware | -0.74 | [-1.08, -0.42] | yes |
| 0.5 | best schedule | -1.45 | [-1.99, -0.92] | yes |
| 0.5 | best classical incl. spread-aware | -1.33 | [-1.84, -0.86] | yes |
| 0.75 | best schedule | -1.16 | [-1.76, -0.60] | yes |
| 0.75 | best classical incl. spread-aware | -0.87 | [-1.59, -0.36] | yes |
| 1 | best schedule | -0.76 | [-1.23, -0.30] | yes |
| 1 | best classical incl. spread-aware | -0.49 | [-1.11, -0.00] | yes |

POV 5% and 7.5% may be off the top of the plot (it cannot finish orders of 5% ADV cleanly). See `frontier_urgency.png`.
