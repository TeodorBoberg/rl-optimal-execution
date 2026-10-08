# RL urgency frontier vs Almgren-Chriss

Run configuration: `overrides: market.permanent_impact_mode=cumulative, market.impact_volume_ref=bar, reward_weights.disable_alpha_signal=true, execution.enable_passive=false, execution.action_squash=sigmoid, execution.drop_noise_obs=true`

Pairing with the benchmark episodes: PASS. Signed implementation shortfall. Risk = std of per-episode cost within side, averaged over sides.

## Pooled over all folds and runs

| strategy | risk (bps) | mean cost (bps) | finish step | done by 25% |
|---|---|---|---|---|
| RL urgency 0 | 124.4 | 8.77 | 386 | 36% |
| RL urgency 0.25 | 116.7 | 8.66 | 369 | 46% |
| RL urgency 0.5 | 109.6 | 8.89 | 341 | 57% |
| RL urgency 0.75 | 104.0 | 9.23 | 306 | 66% |
| RL urgency 1 | 100.3 | 9.59 | 265 | 74% |
| twap | 132.6 | 8.85 | 390 | 25% |
| vwap | 127.1 | 8.95 | 390 | 32% |
| ac@0.01 | 131.6 | 8.84 | 390 | 26% |
| ac@0.05 | 128.4 | 8.85 | 390 | 31% |
| ac@0.2 | 120.5 | 8.99 | 390 | 44% |
| ac@0.6 | 111.7 | 9.35 | 388 | 60% |
| ac@1.5 | 105.2 | 9.77 | 377 | 73% |
| ac@5 | 99.1 | 10.31 | 264 | 85% |
| ac@20 | 95.6 | 10.78 | 162 | 92% |
| pov@5 | 132.4 | 15.02 | 371 | 28% |
| pov@7.5 | 122.5 | 10.79 | 320 | 42% |
| pov@10 | 114.7 | 9.58 | 258 | 54% |
| pov@12.5 | 109.4 | 9.53 | 207 | 65% |
| pov@15 | 105.1 | 9.81 | 166 | 75% |
| pov@17.5 | 101.5 | 10.18 | 135 | 82% |
| pov@20 | 98.8 | 10.55 | 113 | 87% |
| pov@22.5 | 96.5 | 10.92 | 96 | 91% |
| pov@25 | 94.5 | 11.27 | 84 | 94% |

## Agent vs AC at equal risk, per run

Agent mean cost minus AC's mean cost at the same risk, interpolated along that fold's AC curve (same episodes). **Negative = agent is below the AC frontier, i.e. better.** Mean ± std across runs; `below` counts runs with a negative gap. `outside` counts runs whose risk lies beyond the range the benchmark's settings cover; those are compared with the nearest setting (e.g. AC at risk aversion 20) instead of an extrapolated curve.

| urgency | gap vs AC (bps) | runs below AC | outside | gap vs POV curve (bps) | runs below POV | outside |
|---|---|---|---|---|---|---|
| 0 | -0.15 ± 0.26 | 2/3 | 0 | -2.89 ± 0.95 | 3/3 | 0 |
| 0.25 | -0.48 ± 0.11 | 3/3 | 0 | -1.24 ± 0.33 | 3/3 | 0 |
| 0.5 | -0.59 ± 0.05 | 3/3 | 0 | -0.67 ± 0.06 | 3/3 | 0 |
| 0.75 | -0.64 ± 0.06 | 3/3 | 0 | -0.68 ± 0.06 | 3/3 | 0 |
| 1 | -0.61 ± 0.05 | 3/3 | 0 | -0.74 ± 0.07 | 3/3 | 0 |

POV 5% is off the top of the plot (it cannot finish orders of 5% ADV cleanly). See `frontier_urgency.png`.
