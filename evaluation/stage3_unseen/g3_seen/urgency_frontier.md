# RL urgency frontier vs Almgren-Chriss

Run configuration: `overrides: none`

Pairing with the benchmark episodes: PASS. Signed implementation shortfall. Risk = std of per-episode cost within side, averaged over sides.

## Pooled over all folds and runs

| strategy | risk (bps) | mean cost (bps) | finish step | done by 25% |
|---|---|---|---|---|
| RL urgency 0 | 129.7 | 9.75 | 375 | 32% |
| RL urgency 0.25 | 120.7 | 10.00 | 316 | 51% |
| RL urgency 0.5 | 113.2 | 10.93 | 217 | 70% |
| RL urgency 0.75 | 108.4 | 12.22 | 141 | 84% |
| RL urgency 1 | 105.6 | 12.96 | 108 | 90% |
| twap | 130.7 | 9.72 | 390 | 25% |
| vwap | 126.9 | 10.22 | 390 | 32% |
| ac@0.01 | 125.1 | 10.09 | 390 | 36% |
| ac@0.05 | 116.5 | 10.99 | 389 | 56% |
| ac@0.2 | 110.0 | 12.07 | 368 | 75% |
| ac@0.3 | 108.6 | 12.37 | 332 | 79% |
| ac@0.6 | 106.7 | 12.82 | 255 | 85% |
| ac@1 | 105.6 | 13.08 | 212 | 88% |
| ac@1.5 | 105.0 | 13.26 | 186 | 89% |
| ac@2.5 | 104.4 | 13.45 | 160 | 91% |
| ac@5 | 104.0 | 13.65 | 135 | 92% |
| ac@10 | 103.8 | 13.80 | 119 | 92% |
| ac@20 | 103.8 | 13.89 | 108 | 92% |
| acv@0.01 | 120.2 | 10.71 | 390 | 44% |
| acv@0.2 | 106.2 | 12.77 | 388 | 79% |
| acv@0.6 | 104.6 | 13.30 | 303 | 87% |
| acv@1.5 | 104.1 | 13.59 | 206 | 90% |
| acv@5 | 103.7 | 13.82 | 140 | 92% |
| acv@20 | 103.7 | 13.93 | 109 | 92% |
| acl@0.01 | 121.4 | 10.71 | 390 | 44% |
| acl@0.05 | 113.4 | 11.64 | 390 | 61% |
| acl@0.2 | 105.5 | 13.02 | 372 | 79% |
| acl@0.6 | 104.2 | 13.49 | 316 | 87% |
| acl@1 | 104.0 | 13.62 | 277 | 89% |
| acl@1.5 | 103.9 | 13.70 | 245 | 90% |
| acl@2.5 | 103.8 | 13.77 | 205 | 91% |
| acl@5 | 103.7 | 13.84 | 164 | 92% |
| acl@10 | 103.7 | 13.90 | 135 | 92% |
| acl@20 | 103.7 | 13.93 | 117 | 93% |
| pov@5 | 136.0 | 16.70 | 374 | 26% |
| pov@7.5 | 127.9 | 12.67 | 332 | 39% |
| pov@10 | 121.1 | 11.47 | 279 | 52% |
| pov@12.5 | 115.9 | 11.44 | 227 | 62% |
| pov@15 | 112.1 | 11.87 | 181 | 71% |
| pov@17.5 | 109.2 | 12.42 | 147 | 78% |
| pov@20 | 107.2 | 12.96 | 121 | 84% |
| pov@22.5 | 105.4 | 13.51 | 103 | 89% |
| pov@25 | 103.7 | 14.01 | 89 | 93% |
| acs0.5@0.01 | 115.7 | 11.05 | 389 | 57% |
| acs0.5@0.05 | 108.8 | 12.18 | 379 | 73% |
| acs0.5@0.2 | 104.7 | 13.26 | 326 | 85% |
| acs0.5@0.6 | 103.9 | 13.62 | 253 | 89% |
| acs0.5@1.5 | 103.8 | 13.78 | 187 | 91% |
| acs0.5@5 | 103.7 | 13.89 | 132 | 92% |
| acs0.5@20 | 103.7 | 13.95 | 105 | 93% |
| acs1@0.01 | 111.7 | 11.66 | 371 | 69% |
| acs1@0.05 | 107.2 | 12.60 | 333 | 80% |
| acs1@0.2 | 104.5 | 13.41 | 262 | 87% |
| acs1@0.6 | 103.9 | 13.69 | 192 | 90% |
| acs1@1.5 | 103.7 | 13.81 | 145 | 92% |
| acs1@5 | 103.7 | 13.91 | 113 | 92% |
| acs1@20 | 103.6 | 13.96 | 98 | 93% |
| acs2@0.01 | 109.2 | 12.31 | 257 | 79% |
| acs2@0.05 | 106.4 | 12.92 | 215 | 84% |
| acs2@0.2 | 104.4 | 13.49 | 161 | 88% |
| acs2@0.6 | 104.0 | 13.68 | 127 | 90% |
| acs2@1.5 | 103.9 | 13.80 | 111 | 91% |
| acs2@5 | 103.8 | 13.89 | 100 | 92% |
| acs2@20 | 103.7 | 13.94 | 95 | 92% |

## Agent vs each benchmark family at equal risk, per run

Agent mean cost minus the family's mean cost at the same risk, interpolated along the lower convex hull of that fold's curve (same episodes), so a dominated setting cannot flatter the agent. **Negative = agent is below that frontier, i.e. better.** Mean ± std across runs, with the number of runs below. A `*` means at least one run's risk lay outside the family's range and was compared with its nearest setting. `best classical` uses, at each risk, the cheapest of all families; `best schedule` the cheapest excluding the spread-aware ones.

| urgency | AC, time clock | AC, volume clock (expected volume) | AC, volume clock (live volume) | POV | AC live, spread-aware k=0.5 | AC live, spread-aware k=1 | AC live, spread-aware k=2 | best schedule | best classical |
|---|---|---|---|---|---|---|---|---|---|
| 0 | -0.34 ± 0.75 (2/3)* | -0.95 ± 0.75 (3/3)* | -0.96 ± 0.75 (3/3)* | -4.08 ± 1.99 (3/3) | -1.29 ± 0.75 (3/3)* | -1.91 ± 0.75 (3/3)* | -2.56 ± 0.75 (3/3)* | -0.34 ± 0.75 (2/3) | -0.34 ± 0.75 (2/3) |
| 0.25 | -0.54 ± 0.57 (3/3) | -0.80 ± 0.60 (3/3)* | -0.83 ± 0.56 (3/3)* | -1.57 ± 0.80 (3/3) | -1.04 ± 0.73 (3/3)* | -1.66 ± 0.73 (3/3)* | -2.31 ± 0.73 (3/3)* | -0.54 ± 0.57 (3/3) | -0.54 ± 0.57 (3/3) |
| 0.5 | -0.59 ± 0.47 (3/3) | -0.79 ± 0.48 (3/3) | -0.74 ± 0.46 (3/3) | -0.80 ± 0.49 (3/3) | -0.51 ± 0.47 (3/3) | -0.73 ± 0.56 (3/3)* | -1.38 ± 0.56 (3/3)* | -0.59 ± 0.47 (3/3) | -0.51 ± 0.47 (3/3) |
| 0.75 | -0.19 ± 0.21 (2/3) | -0.22 ± 0.21 (2/3) | -0.28 ± 0.21 (3/3) | -0.40 ± 0.21 (3/3) | -0.05 ± 0.21 (2/3) | -0.12 ± 0.21 (2/3) | -0.25 ± 0.21 (3/3) | -0.19 ± 0.21 (2/3) | -0.05 ± 0.21 (2/3) |
| 1 | -0.12 ± 0.08 (3/3) | +0.01 ± 0.10 (1/3) | -0.03 ± 0.08 (2/3) | -0.45 ± 0.09 (3/3) | -0.05 ± 0.08 (2/3) | -0.09 ± 0.09 (3/3) | -0.17 ± 0.09 (3/3) | +0.01 ± 0.10 (1/3) | +0.01 ± 0.10 (1/3) |

### Is the best-classical gap more than sampling noise?

95% interval for the `best classical` gap (averaged over runs), from 1000 bootstrap draws that resample whole ticker-days and re-score every strategy, rebuild every hull and recompute every gap on the same draw. The ± in the table above is only the spread across training seeds; this is the uncertainty from which days happened to be sampled.

| urgency | compared with | gap (bps) | 95% interval | excludes 0 |
|---|---|---|---|---|
| 0 | best schedule | -0.34 | [-0.52, -0.16] | yes |
| 0 | best classical incl. spread-aware | -0.34 | [-0.52, -0.16] | yes |
| 0.25 | best schedule | -0.54 | [-0.80, -0.25] | yes |
| 0.25 | best classical incl. spread-aware | -0.54 | [-0.78, -0.25] | yes |
| 0.5 | best schedule | -0.59 | [-0.98, -0.03] | yes |
| 0.5 | best classical incl. spread-aware | -0.51 | [-0.95, +0.03] | NO |
| 0.75 | best schedule | -0.19 | [-0.63, +0.51] | NO |
| 0.75 | best classical incl. spread-aware | -0.05 | [-0.60, +0.66] | NO |
| 1 | best schedule | +0.01 | [-0.49, +0.56] | NO |
| 1 | best classical incl. spread-aware | +0.01 | [-0.48, +0.65] | NO |

POV 5% and 7.5% may be off the top of the plot (it cannot finish orders of 5% ADV cleanly). See `frontier_urgency.png`.
