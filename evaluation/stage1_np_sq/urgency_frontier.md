# RL urgency frontier vs Almgren-Chriss

Run configuration: `overrides: market.permanent_impact_mode=cumulative, reward_weights.disable_alpha_signal=true, execution.enable_passive=false, execution.action_squash=sigmoid, execution.drop_noise_obs=true`

Pairing with the benchmark episodes: PASS. Signed implementation shortfall. Risk = std of per-episode cost within side, averaged over sides.

## Pooled over all folds and runs

| strategy | risk (bps) | mean cost (bps) | finish step | done by 25% |
|---|---|---|---|---|
| RL urgency 0 | 128.1 | 8.77 | 379 | 32% |
| RL urgency 0.25 | 123.6 | 8.67 | 369 | 38% |
| RL urgency 0.5 | 116.6 | 8.86 | 361 | 48% |
| RL urgency 0.75 | 109.0 | 9.40 | 339 | 60% |
| RL urgency 1 | 103.4 | 10.10 | 296 | 70% |
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
| 0 | +0.46 ± 0.04 | 0/3 | 0 | -8.15 ± 2.34 | 3/3 | 0 |
| 0.25 | +0.25 ± 0.09 | 0/3 | 0 | -5.05 ± 1.58 | 3/3 | 0 |
| 0.5 | +0.14 ± 0.08 | 0/3 | 0 | -2.17 ± 0.33 | 3/3 | 0 |
| 0.75 | +0.14 ± 0.04 | 0/3 | 0 | -1.08 ± 0.04 | 3/3 | 0 |
| 1 | +0.16 ± 0.04 | 0/3 | 0 | -1.00 ± 0.03 | 3/3 | 0 |

POV 5% is off the top of the plot (it cannot finish orders of 5% ADV cleanly). See `frontier_urgency.png`.
