# RL urgency frontier vs Almgren-Chriss

Run configuration: `overrides: market.permanent_impact_mode=cumulative, reward_weights.disable_alpha_signal=true`

Pairing with the benchmark episodes: PASS. Signed implementation shortfall. Risk = std of per-episode cost within side, averaged over sides.

## Pooled over all folds and runs

| strategy | risk (bps) | mean cost (bps) | finish step | done by 25% |
|---|---|---|---|---|
| RL urgency 0 | 117.6 | 7.61 | 343 | 39% |
| RL urgency 0.25 | 116.5 | 6.19 | 337 | 40% |
| RL urgency 0.5 | 115.0 | 5.74 | 320 | 43% |
| RL urgency 0.75 | 110.4 | 6.05 | 282 | 51% |
| RL urgency 1 | 104.0 | 6.80 | 232 | 63% |
| twap | 126.4 | 8.26 | 390 | 25% |
| vwap | 121.4 | 8.83 | 390 | 32% |
| ac@0.01 | 125.5 | 8.26 | 390 | 26% |
| ac@0.05 | 122.3 | 8.28 | 390 | 31% |
| ac@0.2 | 114.7 | 8.49 | 390 | 44% |
| ac@0.6 | 106.2 | 8.99 | 388 | 60% |
| ac@1.5 | 100.0 | 9.63 | 377 | 73% |
| ac@5 | 94.2 | 10.58 | 263 | 86% |
| ac@20 | 90.8 | 11.57 | 162 | 92% |
| pov@5 | 129.0 | 22.59 | 372 | 28% |
| pov@7.5 | 117.6 | 13.54 | 322 | 41% |
| pov@10 | 109.5 | 10.83 | 262 | 54% |
| pov@12.5 | 104.3 | 10.41 | 209 | 65% |
| pov@15 | 100.0 | 10.75 | 167 | 74% |
| pov@17.5 | 96.4 | 11.28 | 136 | 81% |
| pov@20 | 93.6 | 11.84 | 114 | 87% |
| pov@22.5 | 91.4 | 12.38 | 97 | 91% |
| pov@25 | 89.5 | 12.92 | 84 | 94% |

## Agent vs AC at equal risk, per run

Agent mean cost minus AC's mean cost at the same risk, interpolated along that fold's AC curve (same episodes). **Negative = agent is below the AC frontier, i.e. better.** Mean ± std across runs; `below` counts runs with a negative gap. `outside` counts runs whose risk lies beyond the range the benchmark's settings cover; those are compared with the nearest setting (e.g. AC at risk aversion 20) instead of an extrapolated curve.

| urgency | gap vs AC (bps) | runs below AC | outside | gap vs POV curve (bps) | runs below POV | outside |
|---|---|---|---|---|---|---|
| 0 | -0.80 ± 0.71 | 3/3 | 0 | -6.19 ± 1.07 | 3/3 | 0 |
| 0.25 | -2.25 ± 0.35 | 3/3 | 0 | -7.01 ± 0.22 | 3/3 | 0 |
| 0.5 | -2.75 ± 0.08 | 3/3 | 0 | -6.94 ± 0.18 | 3/3 | 0 |
| 0.75 | -2.70 ± 0.06 | 3/3 | 0 | -5.10 ± 0.56 | 3/3 | 0 |
| 1 | -2.41 ± 0.11 | 3/3 | 0 | -3.65 ± 0.17 | 3/3 | 0 |

POV 5% is off the top of the plot (it cannot finish orders of 5% ADV cleanly). See `frontier_urgency.png`.
