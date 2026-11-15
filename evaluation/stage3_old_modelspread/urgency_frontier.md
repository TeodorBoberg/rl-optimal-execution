# RL urgency frontier vs Almgren-Chriss

Run configuration: `overrides: market.spread_source=model`

Pairing with the benchmark episodes: PASS. Signed implementation shortfall. Risk = std of per-episode cost within side, averaged over sides.

## Pooled over all folds and runs

| strategy | risk (bps) | mean cost (bps) | finish step | done by 25% |
|---|---|---|---|---|
| RL urgency 0 | 115.2 | 7.85 | 376 | 39% |
| RL urgency 0.5 | 103.6 | 8.31 | 296 | 60% |
| RL urgency 1 | 95.5 | 9.04 | 193 | 78% |
| twap | 122.2 | 7.88 | 390 | 25% |
| vwap | 117.2 | 8.12 | 390 | 32% |
| ac@0.01 | 116.4 | 7.98 | 390 | 35% |
| ac@0.05 | 106.6 | 8.41 | 389 | 54% |
| ac@0.2 | 98.4 | 9.07 | 372 | 74% |
| ac@0.3 | 96.5 | 9.27 | 342 | 78% |
| ac@0.6 | 94.0 | 9.57 | 266 | 84% |
| ac@1 | 92.6 | 9.75 | 221 | 87% |
| ac@1.5 | 91.7 | 9.87 | 193 | 89% |
| ac@2.5 | 91.0 | 10.00 | 165 | 90% |
| ac@5 | 90.4 | 10.12 | 139 | 91% |
| ac@10 | 90.0 | 10.20 | 122 | 92% |
| ac@20 | 89.8 | 10.25 | 111 | 92% |
| acv@0.01 | 110.4 | 8.28 | 390 | 43% |
| acv@0.2 | 93.4 | 9.45 | 389 | 79% |
| acv@0.6 | 91.0 | 9.84 | 312 | 86% |
| acv@1.5 | 90.3 | 10.04 | 213 | 89% |
| acv@5 | 89.9 | 10.19 | 144 | 91% |
| acv@20 | 89.7 | 10.27 | 112 | 92% |
| acl@0.01 | 109.3 | 8.23 | 390 | 44% |
| acl@0.05 | 99.9 | 8.65 | 388 | 60% |
| acl@0.2 | 91.5 | 9.52 | 367 | 78% |
| acl@0.6 | 90.1 | 9.91 | 309 | 86% |
| acl@1 | 89.9 | 10.02 | 270 | 88% |
| acl@1.5 | 89.8 | 10.09 | 239 | 90% |
| acl@2.5 | 89.7 | 10.15 | 203 | 90% |
| acl@5 | 89.7 | 10.22 | 165 | 91% |
| acl@10 | 89.7 | 10.26 | 138 | 92% |
| acl@20 | 89.7 | 10.29 | 121 | 92% |
| pov@5 | 122.7 | 14.58 | 367 | 28% |
| pov@7.5 | 112.9 | 10.75 | 321 | 41% |
| pov@10 | 106.3 | 9.21 | 265 | 53% |
| pov@12.5 | 101.9 | 8.88 | 215 | 64% |
| pov@15 | 98.6 | 9.05 | 175 | 72% |
| pov@17.5 | 95.8 | 9.35 | 145 | 79% |
| pov@20 | 93.4 | 9.68 | 122 | 85% |
| pov@22.5 | 91.3 | 10.02 | 105 | 89% |
| pov@25 | 89.6 | 10.35 | 91 | 92% |
| acs0.5@0.01 | 107.7 | 8.14 | 390 | 49% |
| acs0.5@0.05 | 98.7 | 8.63 | 386 | 65% |
| acs0.5@0.2 | 91.1 | 9.54 | 354 | 82% |
| acs0.5@0.6 | 90.0 | 9.94 | 279 | 88% |
| acs0.5@1.5 | 89.8 | 10.11 | 210 | 90% |
| acs0.5@5 | 89.7 | 10.23 | 147 | 91% |
| acs0.5@20 | 89.7 | 10.30 | 113 | 92% |
| acs1@0.01 | 105.9 | 8.17 | 390 | 54% |
| acs1@0.05 | 97.7 | 8.70 | 381 | 70% |
| acs1@0.2 | 91.1 | 9.56 | 332 | 84% |
| acs1@0.6 | 90.0 | 9.94 | 246 | 89% |
| acs1@1.5 | 89.8 | 10.10 | 183 | 91% |
| acs1@5 | 89.7 | 10.23 | 133 | 92% |
| acs1@20 | 89.7 | 10.30 | 107 | 92% |
| acs2@0.01 | 103.1 | 8.38 | 384 | 65% |
| acs2@0.05 | 96.4 | 8.93 | 353 | 78% |
| acs2@0.2 | 91.3 | 9.63 | 264 | 87% |
| acs2@0.6 | 90.2 | 9.94 | 186 | 90% |
| acs2@1.5 | 89.9 | 10.07 | 144 | 91% |
| acs2@5 | 89.8 | 10.17 | 115 | 92% |
| acs2@20 | 89.7 | 10.25 | 101 | 92% |

## Agent vs each benchmark family at equal risk, per run

Agent mean cost minus the family's mean cost at the same risk, interpolated along the lower convex hull of that fold's curve (same episodes), so a dominated setting cannot flatter the agent. **Negative = agent is below that frontier, i.e. better.** Mean ± std across runs, with the number of runs below. A `*` means at least one run's risk lay outside the family's range and was compared with its nearest setting. `best classical` uses, at each risk, the cheapest of all families; `best schedule` the cheapest excluding the spread-aware ones.

| urgency | AC, time clock | AC, volume clock (expected volume) | AC, volume clock (live volume) | POV | AC live, spread-aware k=0.5 | AC live, spread-aware k=1 | AC live, spread-aware k=2 | best schedule | best classical |
|---|---|---|---|---|---|---|---|---|---|
| 0 | -0.24 ± 0.13 (12/12)* | -0.43 ± 0.15 (12/12)* | -0.38 ± 0.16 (12/12)* | -3.63 ± 1.84 (12/12)* | -0.30 ± 0.16 (12/12)* | -0.32 ± 0.16 (12/12)* | -0.54 ± 0.17 (12/12)* | -0.24 ± 0.13 (12/12) | -0.23 ± 0.13 (12/12) |
| 0.5 | -0.34 ± 0.13 (12/12) | -0.42 ± 0.17 (12/12)* | -0.16 ± 0.15 (11/12) | -0.75 ± 0.31 (12/12) | -0.05 ± 0.10 (7/12)* | -0.02 ± 0.07 (6/12)* | -0.11 ± 0.09 (12/12)* | -0.16 ± 0.15 (11/12) | -0.01 ± 0.07 (6/12) |
| 1 | -0.36 ± 0.15 (12/12) | -0.26 ± 0.16 (12/12) | -0.05 ± 0.22 (6/12) | -0.36 ± 0.20 (12/12) | +0.03 ± 0.15 (5/12) | +0.05 ± 0.12 (3/12) | -0.03 ± 0.11 (7/12) | -0.05 ± 0.22 (6/12) | +0.07 ± 0.13 (3/12) |

### Is the best-classical gap more than sampling noise?

95% interval for the `best classical` gap (averaged over runs), from 1000 bootstrap draws that resample whole ticker-days and re-score every strategy, rebuild every hull and recompute every gap on the same draw. The ± in the table above is only the spread across training seeds; this is the uncertainty from which days happened to be sampled.

| urgency | compared with | gap (bps) | 95% interval | excludes 0 |
|---|---|---|---|---|
| 0 | best schedule | -0.24 | [-0.32, -0.15] | yes |
| 0 | best classical incl. spread-aware | -0.23 | [-0.31, -0.15] | yes |
| 0.5 | best schedule | -0.16 | [-0.26, -0.07] | yes |
| 0.5 | best classical incl. spread-aware | -0.01 | [-0.09, +0.08] | NO |
| 1 | best schedule | -0.05 | [-0.17, +0.09] | NO |
| 1 | best classical incl. spread-aware | +0.07 | [-0.05, +0.21] | NO |

POV 5% and 7.5% may be off the top of the plot (it cannot finish orders of 5% ADV cleanly). See `frontier_urgency.png`.
