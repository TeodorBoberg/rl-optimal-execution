# RL urgency frontier vs Almgren-Chriss

Pairing with the benchmark episodes: PASS. Signed implementation shortfall. Risk = std of per-episode cost within side, averaged over sides.

## Pooled over all folds and runs

| strategy | risk (bps) | mean cost (bps) | finish step | done by 25% |
|---|---|---|---|---|
| RL urgency 0 | 124.8 | 6.22 | 271 | 26% |
| RL urgency 0.25 | 108.8 | 7.09 | 150 | 71% |
| RL urgency 0.5 | 98.8 | 7.98 | 104 | 91% |
| RL urgency 0.75 | 94.2 | 8.71 | 92 | 93% |
| RL urgency 1 | 92.4 | 9.05 | 88 | 93% |
| twap | 125.2 | 11.94 | 390 | 25% |
| vwap | 120.7 | 12.26 | 390 | 32% |
| ac@0.01 | 124.4 | 11.78 | 390 | 26% |
| ac@0.05 | 121.5 | 11.22 | 390 | 31% |
| ac@0.2 | 114.7 | 9.95 | 390 | 44% |
| ac@0.6 | 107.1 | 8.70 | 388 | 60% |
| ac@1.5 | 101.3 | 8.07 | 377 | 73% |
| ac@5 | 96.1 | 7.97 | 265 | 85% |
| ac@20 | 92.8 | 8.39 | 165 | 91% |
| pov@5 | 127.3 | 24.92 | 369 | 28% |
| pov@7.5 | 115.6 | 15.13 | 318 | 42% |
| pov@10 | 108.4 | 11.16 | 259 | 54% |
| pov@12.5 | 103.9 | 9.64 | 208 | 65% |
| pov@15 | 100.4 | 9.10 | 168 | 74% |
| pov@17.5 | 97.5 | 8.97 | 139 | 81% |
| pov@20 | 95.1 | 9.03 | 116 | 86% |
| pov@22.5 | 93.1 | 9.18 | 100 | 90% |
| pov@25 | 91.4 | 9.39 | 87 | 93% |

## Agent vs AC at equal risk, per run

Agent mean cost minus AC's mean cost at the same risk, interpolated along that fold's AC curve (same episodes). **Negative = agent is below the AC frontier, i.e. better.** Mean ± std across runs; `below` counts runs with a negative gap. `outside` counts runs whose risk lies beyond the range the benchmark's settings cover; those are compared with the nearest setting (e.g. AC at risk aversion 20) instead of an extrapolated curve.

| urgency | gap vs AC (bps) | runs below AC | outside | gap vs POV curve (bps) | runs below POV | outside |
|---|---|---|---|---|---|---|
| 0 | -5.44 ± 1.46 | 12/12 | 6 | -15.04 ± 3.71 | 12/12 | 3 |
| 0.25 | -1.91 ± 0.95 | 12/12 | 0 | -4.77 ± 2.49 | 12/12 | 0 |
| 0.5 | -0.07 ± 0.45 | 6/12 | 0 | -1.29 ± 0.82 | 12/12 | 0 |
| 0.75 | +0.51 ± 0.37 | 1/12 | 1 | -0.41 ± 0.28 | 11/12 | 0 |
| 1 | +0.69 ± 0.27 | 0/12 | 9 | -0.21 ± 0.15 | 11/12 | 1 |

POV 5% is off the top of the plot (it cannot finish orders of 5% ADV cleanly). See `frontier_urgency.png`.
