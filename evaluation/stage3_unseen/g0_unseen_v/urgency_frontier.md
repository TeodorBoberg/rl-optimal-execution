# RL urgency frontier vs Almgren-Chriss

Run configuration: `overrides: none`

Pairing with the benchmark episodes: PASS. Signed implementation shortfall. Risk = std of per-episode cost within side, averaged over sides.

## Pooled over all folds and runs

| strategy | risk (bps) | mean cost (bps) | finish step | done by 25% |
|---|---|---|---|---|
| RL urgency 0 | 126.8 | 11.32 | 362 | 37% |
| RL urgency 0.25 | 118.7 | 11.22 | 295 | 53% |
| RL urgency 0.5 | 110.8 | 11.37 | 227 | 68% |
| RL urgency 0.75 | 102.4 | 11.96 | 159 | 80% |
| RL urgency 1 | 97.0 | 12.70 | 124 | 85% |
| twap | 130.8 | 10.65 | 390 | 25% |
| vwap | 125.8 | 11.23 | 390 | 32% |
| ac@0.01 | 125.3 | 10.93 | 390 | 35% |
| ac@0.05 | 116.0 | 11.64 | 389 | 55% |
| ac@0.2 | 107.3 | 12.49 | 368 | 74% |
| ac@0.3 | 104.9 | 12.72 | 333 | 78% |
| ac@0.6 | 101.3 | 13.09 | 258 | 84% |
| ac@1 | 99.0 | 13.32 | 215 | 87% |
| ac@1.5 | 97.4 | 13.47 | 189 | 88% |
| ac@2.5 | 95.9 | 13.62 | 163 | 90% |
| ac@5 | 94.5 | 13.77 | 139 | 90% |
| ac@10 | 93.8 | 13.86 | 122 | 91% |
| ac@20 | 93.5 | 13.91 | 112 | 91% |
| acv@0.01 | 119.1 | 11.52 | 390 | 44% |
| acv@0.2 | 100.8 | 13.02 | 388 | 79% |
| acv@0.6 | 96.6 | 13.49 | 301 | 86% |
| acv@1.5 | 94.6 | 13.70 | 207 | 89% |
| acv@5 | 93.7 | 13.85 | 143 | 90% |
| acv@20 | 93.3 | 13.93 | 113 | 91% |
| acl@0.01 | 114.6 | 11.34 | 390 | 44% |
| acl@0.05 | 104.3 | 12.01 | 389 | 61% |
| acl@0.2 | 95.8 | 13.15 | 360 | 78% |
| acl@0.6 | 94.1 | 13.56 | 310 | 86% |
| acl@1 | 93.8 | 13.67 | 273 | 88% |
| acl@1.5 | 93.6 | 13.73 | 242 | 89% |
| acl@2.5 | 93.5 | 13.80 | 204 | 90% |
| acl@5 | 93.4 | 13.86 | 165 | 90% |
| acl@10 | 93.3 | 13.90 | 139 | 91% |
| acl@20 | 93.3 | 13.94 | 122 | 91% |
| pov@5 | 128.5 | 20.66 | 363 | 27% |
| pov@7.5 | 118.9 | 14.24 | 327 | 40% |
| pov@10 | 112.5 | 12.29 | 276 | 52% |
| pov@12.5 | 107.4 | 12.10 | 225 | 62% |
| pov@15 | 103.1 | 12.38 | 181 | 71% |
| pov@17.5 | 99.8 | 12.78 | 149 | 78% |
| pov@20 | 97.1 | 13.17 | 125 | 84% |
| pov@22.5 | 94.9 | 13.56 | 107 | 88% |
| pov@25 | 93.2 | 14.01 | 93 | 91% |
| acs0.5@0.01 | 109.4 | 11.28 | 390 | 52% |
| acs0.5@0.05 | 99.8 | 12.18 | 379 | 68% |
| acs0.5@0.2 | 94.5 | 13.21 | 337 | 82% |
| acs0.5@0.6 | 93.7 | 13.57 | 275 | 87% |
| acs0.5@1.5 | 93.4 | 13.73 | 208 | 90% |
| acs0.5@5 | 93.3 | 13.86 | 146 | 91% |
| acs0.5@20 | 93.2 | 13.94 | 113 | 91% |
| acs1@0.01 | 104.7 | 11.59 | 380 | 60% |
| acs1@0.05 | 97.7 | 12.41 | 352 | 73% |
| acs1@0.2 | 94.1 | 13.26 | 299 | 83% |
| acs1@0.6 | 93.6 | 13.59 | 235 | 88% |
| acs1@1.5 | 93.4 | 13.74 | 178 | 90% |
| acs1@5 | 93.3 | 13.86 | 131 | 91% |
| acs1@20 | 93.2 | 13.94 | 107 | 91% |
| acs2@0.01 | 100.6 | 12.07 | 313 | 68% |
| acs2@0.05 | 96.7 | 12.65 | 284 | 77% |
| acs2@0.2 | 94.2 | 13.30 | 234 | 85% |
| acs2@0.6 | 93.8 | 13.56 | 182 | 88% |
| acs2@1.5 | 93.5 | 13.71 | 148 | 90% |
| acs2@5 | 93.3 | 13.82 | 118 | 91% |
| acs2@20 | 93.2 | 13.91 | 104 | 91% |

## Agent vs each benchmark family at equal risk, per run

Agent mean cost minus the family's mean cost at the same risk, interpolated along the lower convex hull of that fold's curve (same episodes), so a dominated setting cannot flatter the agent. **Negative = agent is below that frontier, i.e. better.** Mean ± std across runs, with the number of runs below. A `*` means at least one run's risk lay outside the family's range and was compared with its nearest setting. `best classical` uses, at each risk, the cheapest of all families; `best schedule` the cheapest excluding the spread-aware ones.

| urgency | AC, time clock | AC, volume clock (expected volume) | AC, volume clock (live volume) | POV | AC live, spread-aware k=0.5 | AC live, spread-aware k=1 | AC live, spread-aware k=2 | best schedule | best classical |
|---|---|---|---|---|---|---|---|---|---|
| 0 | +0.33 ± 0.22 (0/3)* | -0.21 ± 0.24 (3/3)* | -0.02 ± 0.24 (1/3)* | -7.87 ± 2.05 (3/3)* | +0.04 ± 0.24 (1/3)* | -0.27 ± 0.24 (3/3)* | -0.76 ± 0.24 (3/3)* | +0.33 ± 0.22 (0/3) | +0.33 ± 0.22 (0/3) |
| 0.25 | -0.21 ± 0.20 (3/3) | -0.39 ± 0.17 (3/3)* | -0.12 ± 0.29 (2/3)* | -3.32 ± 1.43 (3/3) | -0.05 ± 0.29 (2/3)* | -0.36 ± 0.29 (3/3)* | -0.85 ± 0.29 (3/3)* | -0.09 ± 0.30 (2/3) | -0.04 ± 0.29 (2/3) |
| 0.5 | -0.77 ± 0.20 (3/3) | -0.82 ± 0.22 (3/3) | -0.21 ± 0.25 (2/3) | -0.86 ± 0.44 (3/3) | +0.07 ± 0.33 (1/3)* | -0.22 ± 0.37 (2/3)* | -0.70 ± 0.37 (3/3)* | -0.21 ± 0.25 (2/3) | +0.07 ± 0.33 (1/3) |
| 0.75 | -1.01 ± 0.28 (3/3) | -0.93 ± 0.30 (3/3) | -0.31 ± 0.24 (3/3) | -0.52 ± 0.28 (3/3) | +0.03 ± 0.29 (1/3) | +0.10 ± 0.26 (1/3) | -0.12 ± 0.42 (2/3)* | -0.31 ± 0.24 (3/3) | +0.10 ± 0.26 (1/3) |
| 1 | -0.80 ± 0.23 (3/3) | -0.73 ± 0.23 (3/3) | -0.28 ± 0.24 (3/3) | -0.49 ± 0.25 (3/3) | -0.00 ± 0.26 (2/3) | +0.13 ± 0.28 (1/3) | +0.07 ± 0.27 (2/3) | -0.28 ± 0.24 (3/3) | +0.13 ± 0.28 (1/3) |

### Is the best-classical gap more than sampling noise?

95% interval for the `best classical` gap (averaged over runs), from 1000 bootstrap draws that resample whole ticker-days and re-score every strategy, rebuild every hull and recompute every gap on the same draw. The ± in the table above is only the spread across training seeds; this is the uncertainty from which days happened to be sampled.

| urgency | compared with | gap (bps) | 95% interval | excludes 0 |
|---|---|---|---|---|
| 0 | best schedule | +0.33 | [+0.11, +0.55] | yes |
| 0 | best classical incl. spread-aware | +0.33 | [+0.11, +0.56] | yes |
| 0.25 | best schedule | -0.09 | [-0.27, +0.13] | NO |
| 0.25 | best classical incl. spread-aware | -0.04 | [-0.25, +0.21] | NO |
| 0.5 | best schedule | -0.21 | [-0.52, +0.05] | NO |
| 0.5 | best classical incl. spread-aware | +0.07 | [-0.15, +0.24] | NO |
| 0.75 | best schedule | -0.31 | [-0.74, +0.09] | NO |
| 0.75 | best classical incl. spread-aware | +0.10 | [-0.21, +0.38] | NO |
| 1 | best schedule | -0.28 | [-0.66, +0.22] | NO |
| 1 | best classical incl. spread-aware | +0.13 | [-0.19, +0.53] | NO |

POV 5% and 7.5% may be off the top of the plot (it cannot finish orders of 5% ADV cleanly). See `frontier_urgency.png`.
