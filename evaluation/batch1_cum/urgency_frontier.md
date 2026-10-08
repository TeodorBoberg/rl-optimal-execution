# RL urgency frontier vs Almgren-Chriss

Run configuration: `overrides: market.permanent_impact_mode=cumulative`

Pairing with the benchmark episodes: PASS. Signed implementation shortfall. Risk = std of per-episode cost within side, averaged over sides.

## Pooled over all folds and runs

| strategy | risk (bps) | mean cost (bps) | finish step | done by 25% |
|---|---|---|---|---|
| RL urgency 0 | 124.8 | 8.20 | 271 | 26% |
| RL urgency 0.25 | 108.8 | 9.54 | 150 | 71% |
| RL urgency 0.5 | 98.8 | 10.70 | 104 | 91% |
| RL urgency 0.75 | 94.2 | 11.56 | 92 | 93% |
| RL urgency 1 | 92.5 | 11.95 | 88 | 93% |
| twap | 125.2 | 8.21 | 390 | 25% |
| vwap | 120.7 | 8.71 | 390 | 32% |
| ac@0.01 | 124.4 | 8.20 | 390 | 26% |
| ac@0.05 | 121.5 | 8.21 | 390 | 31% |
| ac@0.2 | 114.7 | 8.38 | 390 | 44% |
| ac@0.6 | 107.1 | 8.82 | 388 | 60% |
| ac@1.5 | 101.3 | 9.39 | 377 | 73% |
| ac@5 | 96.1 | 10.24 | 265 | 85% |
| ac@20 | 92.8 | 11.12 | 165 | 91% |
| pov@5 | 127.1 | 21.06 | 369 | 28% |
| pov@7.5 | 115.5 | 13.24 | 318 | 42% |
| pov@10 | 108.3 | 10.77 | 259 | 54% |
| pov@12.5 | 103.8 | 10.32 | 208 | 65% |
| pov@15 | 100.4 | 10.53 | 168 | 74% |
| pov@17.5 | 97.5 | 10.94 | 139 | 81% |
| pov@20 | 95.1 | 11.40 | 116 | 86% |
| pov@22.5 | 93.1 | 11.86 | 100 | 90% |
| pov@25 | 91.4 | 12.31 | 87 | 93% |

## Agent vs AC at equal risk, per run

Agent mean cost minus AC's mean cost at the same risk, interpolated along that fold's AC curve (same episodes). **Negative = agent is below the AC frontier, i.e. better.** Mean ± std across runs; `below` counts runs with a negative gap. `outside` counts runs whose risk lies beyond the range the benchmark's settings cover; those are compared with the nearest setting (e.g. AC at risk aversion 20) instead of an extrapolated curve.

| urgency | gap vs AC (bps) | runs below AC | outside | gap vs POV curve (bps) | runs below POV | outside |
|---|---|---|---|---|---|---|
| 0 | -0.00 ± 0.89 | 8/12 | 6 | -9.87 ± 3.47 | 12/12 | 3 |
| 0.25 | +0.81 ± 0.60 | 1/12 | 0 | -1.71 ± 1.53 | 11/12 | 0 |
| 0.5 | +0.89 ± 0.46 | 0/12 | 0 | -0.13 ± 0.39 | 7/12 | 0 |
| 0.75 | +0.85 ± 0.34 | 0/12 | 1 | -0.02 ± 0.18 | 7/12 | 0 |
| 1 | +0.88 ± 0.28 | 0/12 | 9 | -0.07 ± 0.09 | 9/12 | 1 |

POV 5% is off the top of the plot (it cannot finish orders of 5% ADV cleanly). See `frontier_urgency.png`.
