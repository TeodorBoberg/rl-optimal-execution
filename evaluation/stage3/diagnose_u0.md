# Agent (no guardrail) vs TWAP at urgency 0, paired episodes

Run: `evaluation\stage3`. Gap = agent - TWAP in bps, positive = agent worse. Agent averaged over model seeds. Unmatched days: 0.0%.

## Per fold

| fold | episodes | gap | execution | drift | permanent | fees | done@25% | done@50% | done@75% | finish step | participation | test vol / train ADV | test spread / train avg |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 800 | +1.96 | +2.06 | -0.10 | -0.00 | -0.00 | 35% | 56% | 74% | 348 | 0.069 | 0.95 | 0.69 |
| 1 | 800 | +10.02 | +10.04 | -0.02 | -0.00 | -0.00 | 30% | 45% | 60% | 389 | 0.090 | 0.64 | 0.90 |
| 2 | 800 | +2.41 | +2.36 | +0.05 | +0.00 | -0.00 | 35% | 55% | 74% | 370 | 0.081 | 0.82 | 0.70 |
| 3 | 800 | +2.37 | +2.31 | +0.05 | -0.00 | -0.00 | 32% | 52% | 72% | 373 | 0.077 | 0.78 | 1.14 |

## Gap by tercile of day volume / training ADV (terciles within each fold)

| fold | low | mid | high | corr(gap, log feature) |
|---|---:|---:|---:|---:|
| 0 | +6.13 | -0.08 | -0.20 | -0.19 |
| 1 | +17.92 | +6.52 | +5.48 | -0.08 |
| 2 | +4.49 | +2.45 | +0.22 | -0.09 |
| 3 | +3.72 | +2.78 | +0.58 | -0.06 |

## Gap by tercile of day mean spread / training average spread (terciles within each fold)

| fold | low | mid | high | corr(gap, log feature) |
|---|---:|---:|---:|---:|
| 0 | +0.16 | -0.19 | +5.93 | +0.20 |
| 1 | -0.01 | +0.76 | +29.62 | +0.22 |
| 2 | +0.32 | +0.49 | +6.41 | +0.15 |
| 3 | +0.15 | +0.55 | +6.42 | +0.17 |

## Gap by tercile of first-30-min spread / day mean spread (terciles within each fold)

| fold | low | mid | high | corr(gap, log feature) |
|---|---:|---:|---:|---:|
| 0 | +2.20 | +2.40 | +1.28 | -0.00 |
| 1 | +16.62 | +11.25 | +2.14 | -0.08 |
| 2 | +4.25 | +2.61 | +0.34 | -0.08 |
| 3 | +3.28 | +2.45 | +1.36 | -0.05 |

## Worst tickers (all folds)

| ticker | episodes | gap |
|---|---:|---:|
| jpm | 224 | +22.23 |
| cvx | 272 | +9.82 |
| msft | 264 | +8.09 |
| tsla | 208 | +8.06 |
| pg | 304 | +5.20 |
| xom | 232 | +0.58 |
| aapl | 160 | +0.47 |
| wmt | 320 | +0.29 |
| googl | 200 | +0.12 |
| qqq | 200 | +0.12 |
| spy | 256 | +0.11 |
| nvda | 256 | -0.03 |
| bac | 304 | -0.04 |
