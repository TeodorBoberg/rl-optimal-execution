# Agent (no guardrail) vs TWAP at urgency 0, paired episodes

Run: `evaluation\stage3b`. Gap = agent - TWAP in bps, positive = agent worse. Agent averaged over model seeds. Unmatched days: 0.0%.

## Per fold

| fold | episodes | gap | execution | drift | permanent | fees | done@25% | done@50% | done@75% | finish step | participation | test vol / train ADV | test spread / train avg |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 800 | +1.85 | +2.13 | -0.28 | -0.00 | -0.00 | 35% | 53% | 65% | 359 | 0.065 | 0.95 | 0.69 |
| 1 | 800 | +24.41 | +24.42 | -0.01 | -0.00 | -0.00 | 16% | 22% | 26% | 390 | 0.091 | 0.64 | 0.90 |
| 2 | 800 | +8.21 | +8.16 | +0.05 | +0.00 | -0.00 | 35% | 47% | 56% | 390 | 0.072 | 0.82 | 0.70 |
| 3 | 800 | +1.91 | +1.93 | -0.03 | -0.00 | -0.00 | 46% | 66% | 78% | 379 | 0.073 | 0.78 | 1.14 |

## Gap by tercile of day volume / training ADV (terciles within each fold)

| fold | low | mid | high | corr(gap, log feature) |
|---|---:|---:|---:|---:|
| 0 | +4.62 | +0.88 | +0.02 | -0.15 |
| 1 | +41.48 | +17.20 | +14.23 | -0.15 |
| 2 | +16.59 | +5.87 | +2.00 | -0.24 |
| 3 | +3.50 | +1.42 | +0.78 | -0.06 |

## Gap by tercile of day mean spread / training average spread (terciles within each fold)

| fold | low | mid | high | corr(gap, log feature) |
|---|---:|---:|---:|---:|
| 0 | +0.67 | +0.09 | +4.80 | +0.13 |
| 1 | +7.08 | +14.70 | +51.91 | +0.28 |
| 2 | +1.31 | +7.43 | +15.93 | +0.25 |
| 3 | +0.38 | +1.61 | +3.75 | +0.07 |

## Gap by tercile of first-30-min spread / day mean spread (terciles within each fold)

| fold | low | mid | high | corr(gap, log feature) |
|---|---:|---:|---:|---:|
| 0 | +1.93 | +2.56 | +1.06 | -0.01 |
| 1 | +33.30 | +26.17 | +13.69 | -0.09 |
| 2 | +9.94 | +10.42 | +4.26 | -0.09 |
| 3 | +2.69 | +1.85 | +1.17 | -0.03 |

## Worst tickers (all folds)

| ticker | episodes | gap |
|---|---:|---:|
| tsla | 208 | +34.51 |
| jpm | 224 | +29.20 |
| msft | 264 | +17.19 |
| cvx | 272 | +11.22 |
| pg | 304 | +10.12 |
| nvda | 256 | +5.88 |
| googl | 200 | +5.14 |
| aapl | 160 | +4.90 |
| bac | 304 | +1.26 |
| wmt | 320 | +1.10 |
| xom | 232 | +1.08 |
| spy | 256 | +1.00 |
| qqq | 200 | +0.76 |
