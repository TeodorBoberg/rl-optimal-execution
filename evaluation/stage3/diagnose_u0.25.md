# Agent (no guardrail) vs TWAP at urgency 0.25, paired episodes

Run: `evaluation\stage3`. Gap = agent - TWAP in bps, positive = agent worse. Agent averaged over model seeds. Unmatched days: 0.0%.

## Per fold

| fold | episodes | gap | execution | drift | permanent | fees | done@25% | done@50% | done@75% | finish step | participation | test vol / train ADV | test spread / train avg |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 800 | +1.04 | +1.16 | -0.12 | -0.00 | -0.00 | 59% | 83% | 94% | 244 | 0.097 | 0.95 | 0.69 |
| 1 | 800 | +5.29 | +5.28 | +0.01 | -0.00 | -0.00 | 45% | 62% | 78% | 349 | 0.105 | 0.64 | 0.90 |
| 2 | 800 | +0.64 | +0.59 | +0.04 | +0.00 | -0.00 | 52% | 74% | 89% | 310 | 0.097 | 0.82 | 0.70 |
| 3 | 800 | +0.53 | +0.50 | +0.03 | -0.00 | -0.00 | 51% | 74% | 90% | 313 | 0.095 | 0.78 | 1.14 |

## Gap by tercile of day volume / training ADV (terciles within each fold)

| fold | low | mid | high | corr(gap, log feature) |
|---|---:|---:|---:|---:|
| 0 | +2.64 | +0.28 | +0.19 | -0.05 |
| 1 | +8.94 | +3.46 | +3.39 | -0.04 |
| 2 | +0.84 | +0.76 | +0.31 | -0.00 |
| 3 | +0.69 | +0.71 | +0.19 | -0.00 |

## Gap by tercile of day mean spread / training average spread (terciles within each fold)

| fold | low | mid | high | corr(gap, log feature) |
|---|---:|---:|---:|---:|
| 0 | +0.10 | +0.16 | +2.86 | +0.06 |
| 1 | +0.24 | +0.59 | +15.18 | +0.14 |
| 2 | +0.65 | +0.69 | +0.57 | +0.01 |
| 3 | +0.36 | +0.48 | +0.76 | +0.01 |

## Gap by tercile of first-30-min spread / day mean spread (terciles within each fold)

| fold | low | mid | high | corr(gap, log feature) |
|---|---:|---:|---:|---:|
| 0 | +1.16 | +1.15 | +0.81 | +0.00 |
| 1 | +9.27 | +5.61 | +0.95 | -0.05 |
| 2 | +0.84 | +0.28 | +0.78 | -0.00 |
| 3 | +0.46 | +0.54 | +0.60 | -0.00 |

## Worst tickers (all folds)

| ticker | episodes | gap |
|---|---:|---:|
| jpm | 224 | +9.22 |
| cvx | 272 | +4.21 |
| msft | 264 | +3.94 |
| pg | 304 | +2.36 |
| tsla | 208 | +1.27 |
| wmt | 320 | +0.97 |
| aapl | 160 | +0.68 |
| xom | 232 | +0.55 |
| bac | 304 | +0.35 |
| qqq | 200 | +0.29 |
| spy | 256 | +0.21 |
| googl | 200 | +0.16 |
| nvda | 256 | -0.15 |
