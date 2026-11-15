# RL urgency frontier vs Almgren-Chriss

Run configuration: `overrides: none`

Pairing with the benchmark episodes: PASS. Signed implementation shortfall. Risk = std of per-episode cost within side, averaged over sides.

## Pooled over all folds and runs

| strategy | risk (bps) | mean cost (bps) | finish step | done by 25% |
|---|---|---|---|---|
| RL urgency 0 | 81.2 | 7.75 | 356 | 41% |
| RL urgency 0.25 | 69.4 | 8.15 | 254 | 63% |
| RL urgency 0.5 | 61.4 | 8.71 | 162 | 82% |
| RL urgency 0.75 | 57.9 | 9.32 | 107 | 91% |
| RL urgency 1 | 56.4 | 9.69 | 88 | 93% |
| twap | 89.4 | 7.70 | 390 | 25% |
| vwap | 85.4 | 7.84 | 390 | 33% |
| ac@0.01 | 83.2 | 7.82 | 390 | 36% |
| ac@0.05 | 73.1 | 8.18 | 389 | 56% |
| ac@0.2 | 64.5 | 8.73 | 365 | 76% |
| ac@0.3 | 62.6 | 8.91 | 326 | 81% |
| ac@0.6 | 59.7 | 9.21 | 248 | 87% |
| ac@1 | 58.1 | 9.42 | 204 | 90% |
| ac@1.5 | 57.2 | 9.57 | 178 | 91% |
| ac@2.5 | 56.3 | 9.75 | 152 | 92% |
| ac@5 | 55.6 | 9.92 | 127 | 93% |
| ac@10 | 55.3 | 10.01 | 111 | 93% |
| ac@20 | 55.2 | 10.07 | 100 | 93% |
| acv@0.01 | 77.8 | 8.06 | 390 | 45% |
| acv@0.2 | 58.7 | 9.34 | 388 | 81% |
| acv@0.6 | 56.0 | 9.73 | 287 | 89% |
| acv@1.5 | 55.4 | 9.92 | 191 | 92% |
| acv@5 | 55.2 | 10.03 | 129 | 93% |
| acv@20 | 55.2 | 10.09 | 100 | 93% |
| acl@0.01 | 76.8 | 8.06 | 390 | 45% |
| acl@0.05 | 65.3 | 8.71 | 389 | 64% |
| acl@0.2 | 56.4 | 9.56 | 366 | 82% |
| acl@0.6 | 55.3 | 9.83 | 281 | 89% |
| acl@1 | 55.2 | 9.91 | 240 | 91% |
| acl@1.5 | 55.2 | 9.96 | 209 | 92% |
| acl@2.5 | 55.2 | 10.01 | 177 | 92% |
| acl@5 | 55.2 | 10.05 | 143 | 93% |
| acl@10 | 55.2 | 10.08 | 120 | 93% |
| acl@20 | 55.2 | 10.10 | 106 | 93% |
| pov@5 | 87.9 | 8.62 | 370 | 29% |
| pov@7.5 | 77.9 | 8.15 | 303 | 44% |
| pov@10 | 71.2 | 8.40 | 243 | 57% |
| pov@12.5 | 66.8 | 8.71 | 194 | 68% |
| pov@15 | 63.5 | 9.03 | 157 | 77% |
| pov@17.5 | 60.8 | 9.32 | 129 | 83% |
| pov@20 | 58.5 | 9.61 | 108 | 88% |
| pov@22.5 | 56.8 | 9.88 | 93 | 91% |
| pov@25 | 55.2 | 10.15 | 81 | 94% |
| acs0.5@0.01 | 72.8 | 8.14 | 390 | 51% |
| acs0.5@0.05 | 62.2 | 8.93 | 385 | 69% |
| acs0.5@0.2 | 56.0 | 9.66 | 341 | 84% |
| acs0.5@0.6 | 55.3 | 9.88 | 257 | 90% |
| acs0.5@1.5 | 55.2 | 9.98 | 195 | 92% |
| acs0.5@5 | 55.2 | 10.07 | 136 | 93% |
| acs0.5@20 | 55.2 | 10.11 | 102 | 93% |
| acs1@0.01 | 69.2 | 8.37 | 388 | 58% |
| acs1@0.05 | 60.4 | 9.14 | 370 | 74% |
| acs1@0.2 | 55.8 | 9.74 | 308 | 86% |
| acs1@0.6 | 55.3 | 9.92 | 237 | 90% |
| acs1@1.5 | 55.2 | 10.00 | 183 | 92% |
| acs1@5 | 55.2 | 10.07 | 130 | 93% |
| acs1@20 | 55.2 | 10.12 | 100 | 93% |
| acs2@0.01 | 64.9 | 8.80 | 348 | 68% |
| acs2@0.05 | 59.1 | 9.36 | 313 | 78% |
| acs2@0.2 | 55.8 | 9.83 | 263 | 87% |
| acs2@0.6 | 55.4 | 9.96 | 211 | 91% |
| acs2@1.5 | 55.3 | 10.02 | 167 | 92% |
| acs2@5 | 55.2 | 10.07 | 123 | 93% |
| acs2@20 | 55.2 | 10.12 | 97 | 93% |

## Agent vs each benchmark family at equal risk, per run

Agent mean cost minus the family's mean cost at the same risk, interpolated along the lower convex hull of that fold's curve (same episodes), so a dominated setting cannot flatter the agent. **Negative = agent is below that frontier, i.e. better.** Mean ± std across runs, with the number of runs below. A `*` means at least one run's risk lay outside the family's range and was compared with its nearest setting. `best classical` uses, at each risk, the cheapest of all families; `best schedule` the cheapest excluding the spread-aware ones.

| urgency | AC, time clock | AC, volume clock (expected volume) | AC, volume clock (live volume) | POV | AC live, spread-aware k=0.5 | AC live, spread-aware k=1 | AC live, spread-aware k=2 | best schedule | best classical |
|---|---|---|---|---|---|---|---|---|---|
| 0 | -0.22 ± 0.23 (2/3)* | -0.35 ± 0.26 (3/3)* | -0.32 ± 0.25 (3/3)* | -0.58 ± 0.44 (3/3)* | -0.39 ± 0.25 (3/3)* | -0.62 ± 0.25 (3/3)* | -1.04 ± 0.25 (3/3)* | -0.22 ± 0.23 (2/3) | -0.22 ± 0.23 (2/3) |
| 0.25 | -0.29 ± 0.19 (3/3) | -0.47 ± 0.21 (3/3) | -0.33 ± 0.17 (3/3) | -0.43 ± 0.21 (3/3) | -0.30 ± 0.19 (3/3)* | -0.37 ± 0.19 (3/3)* | -0.64 ± 0.20 (3/3)* | -0.29 ± 0.19 (3/3) | -0.28 ± 0.20 (3/3) |
| 0.5 | -0.32 ± 0.14 (3/3) | -0.44 ± 0.09 (3/3) | -0.36 ± 0.13 (3/3) | -0.55 ± 0.15 (3/3) | -0.32 ± 0.15 (3/3) | -0.34 ± 0.13 (3/3) | -0.42 ± 0.13 (3/3) | -0.32 ± 0.14 (3/3) | -0.31 ± 0.14 (3/3) |
| 0.75 | -0.14 ± 0.05 (3/3) | -0.13 ± 0.06 (3/3) | -0.09 ± 0.04 (3/3) | -0.38 ± 0.06 (3/3) | -0.11 ± 0.04 (3/3) | -0.14 ± 0.05 (3/3) | -0.21 ± 0.05 (3/3) | -0.09 ± 0.04 (3/3) | -0.09 ± 0.04 (3/3) |
| 1 | -0.04 ± 0.13 (2/3) | +0.01 ± 0.13 (1/3) | +0.11 ± 0.12 (1/3) | -0.25 ± 0.13 (3/3) | +0.08 ± 0.13 (1/3) | +0.03 ± 0.13 (1/3) | -0.05 ± 0.13 (2/3) | +0.11 ± 0.12 (1/3) | +0.11 ± 0.12 (1/3) |

### Is the best-classical gap more than sampling noise?

95% interval for the `best classical` gap (averaged over runs), from 1000 bootstrap draws that resample whole ticker-days and re-score every strategy, rebuild every hull and recompute every gap on the same draw. The ± in the table above is only the spread across training seeds; this is the uncertainty from which days happened to be sampled.

| urgency | compared with | gap (bps) | 95% interval | excludes 0 |
|---|---|---|---|---|
| 0 | best schedule | -0.22 | [-0.32, -0.10] | yes |
| 0 | best classical incl. spread-aware | -0.22 | [-0.32, -0.10] | yes |
| 0.25 | best schedule | -0.29 | [-0.51, -0.08] | yes |
| 0.25 | best classical incl. spread-aware | -0.28 | [-0.48, -0.04] | yes |
| 0.5 | best schedule | -0.32 | [-0.59, -0.08] | yes |
| 0.5 | best classical incl. spread-aware | -0.31 | [-0.59, -0.04] | yes |
| 0.75 | best schedule | -0.09 | [-0.28, +0.14] | NO |
| 0.75 | best classical incl. spread-aware | -0.09 | [-0.28, +0.17] | NO |
| 1 | best schedule | +0.11 | [-0.09, +0.37] | NO |
| 1 | best classical incl. spread-aware | +0.11 | [-0.09, +0.39] | NO |

POV 5% and 7.5% may be off the top of the plot (it cannot finish orders of 5% ADV cleanly). See `frontier_urgency.png`.
