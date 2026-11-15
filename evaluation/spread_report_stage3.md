# Spread variation: real data vs simulator

r = spread / that ticker-day's median spread. Lag-k ACF is the within-day autocorrelation of log r: lag 1 is how well the previous minute's spread predicts this minute's, which is the information a trader can use.

Real data: `data/walkforward/fold3.csv`. Simulator config: `configs\stage3\fold3.yaml`.

| statistic | real data | simulator |
|---|---|---|
| ticker_days | 2,000 | 200 |
| minutes | 780,000 | 77,800 |
| median spread (bps) | 1.742 | 1.630 |
| r p5 | 0.499 | 0.500 |
| r p25 | 0.860 | 0.987 |
| r p75 | 1.313 | 1.201 |
| r p95 | 2.844 | 2.507 |
| r p99 | 7.766 | 6.982 |
| share r>1.5 | 18.12% | 15.92% |
| share r>2 | 9.71% | 8.39% |
| share r>3 | 4.44% | 3.58% |
| share r>5 | 1.96% | 1.58% |
| acf lag 1 | 0.471 | 0.519 |
| acf lag 5 | 0.345 | 0.383 |
| acf lag 15 | 0.276 | 0.308 |
| corr(log r, log vol15) | 0.214 | 0.241 |

## Intraday shape (median r per 30-minute bucket)

| minutes | real data | simulator |
|---|---|---|
| 0-29 | 1.76 | 1.70 |
| 30-59 | 1.24 | 1.03 |
| 60-89 | 1.00 | 1.00 |
| 90-119 | 1.00 | 1.00 |
| 120-149 | 1.00 | 1.00 |
| 150-179 | 1.00 | 1.00 |
| 180-209 | 1.00 | 1.00 |
| 210-239 | 1.00 | 1.00 |
| 240-269 | 1.00 | 1.00 |
| 270-299 | 1.00 | 1.00 |
| 300-329 | 1.00 | 1.00 |
| 330-359 | 1.00 | 1.00 |
| 360-389 | 0.99 | 1.00 |
