# RL urgency frontier vs Almgren-Chriss

Run configuration: `overrides: market.permanent_impact_mode=cumulative, reward_weights.disable_alpha_signal=true, execution.enable_passive=false`

Pairing with the benchmark episodes: PASS. Signed implementation shortfall. Risk = std of per-episode cost within side, averaged over sides.

## Pooled over all folds and runs

| strategy | risk (bps) | mean cost (bps) | finish step | done by 25% |
|---|---|---|---|---|
| RL urgency 0 | 96.8 | 12.58 | 152 | 84% |
| RL urgency 0.25 | 95.7 | 12.67 | 134 | 87% |
| RL urgency 0.5 | 95.1 | 12.78 | 117 | 90% |
| RL urgency 0.75 | 94.8 | 12.88 | 101 | 92% |
| RL urgency 1 | 94.6 | 12.95 | 89 | 94% |
| twap | 132.6 | 8.27 | 390 | 25% |
| vwap | 127.1 | 8.81 | 390 | 32% |
| ac@0.01 | 131.6 | 8.27 | 390 | 26% |
| ac@0.05 | 128.4 | 8.29 | 390 | 31% |
| ac@0.2 | 120.5 | 8.50 | 390 | 44% |
| ac@0.6 | 111.7 | 9.00 | 388 | 60% |
| ac@1.5 | 105.2 | 9.64 | 377 | 73% |
| ac@5 | 99.1 | 10.61 | 264 | 85% |
| ac@20 | 95.6 | 11.63 | 162 | 92% |
| pov@5 | 133.1 | 20.68 | 371 | 28% |
| pov@7.5 | 122.6 | 12.64 | 320 | 42% |
| pov@10 | 114.7 | 10.51 | 258 | 54% |
| pov@12.5 | 109.4 | 10.39 | 207 | 65% |
| pov@15 | 105.1 | 10.82 | 166 | 75% |
| pov@17.5 | 101.5 | 11.34 | 135 | 82% |
| pov@20 | 98.8 | 11.89 | 113 | 87% |
| pov@22.5 | 96.5 | 12.46 | 96 | 91% |
| pov@25 | 94.6 | 13.01 | 84 | 94% |

## Agent vs AC at equal risk, per run

Agent mean cost minus AC's mean cost at the same risk, interpolated along that fold's AC curve (same episodes). **Negative = agent is below the AC frontier, i.e. better.** Mean ± std across runs; `below` counts runs with a negative gap. `outside` counts runs whose risk lies beyond the range the benchmark's settings cover; those are compared with the nearest setting (e.g. AC at risk aversion 20) instead of an extrapolated curve.

| urgency | gap vs AC (bps) | runs below AC | outside | gap vs POV curve (bps) | runs below POV | outside |
|---|---|---|---|---|---|---|
| 0 | +1.40 ± 0.05 | 0/3 | 2 | +0.11 ± 0.19 | 1/3 | 0 |
| 0.25 | +1.28 ± 0.16 | 0/3 | 2 | -0.02 ± 0.04 | 2/3 | 0 |
| 0.5 | +1.19 ± 0.31 | 0/3 | 2 | -0.07 ± 0.15 | 2/3 | 1 |
| 0.75 | +1.25 ± 0.21 | 0/3 | 3 | -0.05 ± 0.12 | 1/3 | 1 |
| 1 | +1.31 ± 0.09 | 0/3 | 3 | -0.03 ± 0.07 | 1/3 | 1 |

POV 5% is off the top of the plot (it cannot finish orders of 5% ADV cleanly). See `frontier_urgency.png`.
