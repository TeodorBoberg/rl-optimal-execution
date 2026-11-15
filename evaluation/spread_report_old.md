# Spread variation: real data vs simulator

r = spread / that ticker-day's median spread. Lag-k ACF is the within-day autocorrelation of log r: lag 1 is how well the previous minute's spread predicts this minute's, which is the information a trader can use.

Real data: `data/walkforward/fold3.csv`. Simulator config: `configs\stage2_np_sq_ho\fold3.yaml`.

| statistic | real data | simulator |
|---|---|---|
| ticker_days | 2,000 | 200 |
| minutes | 780,000 | 77,800 |
| median spread (bps) | 1.742 | 2.835 |
| r p5 | 0.499 | 0.632 |
| r p25 | 0.860 | 0.768 |
| r p75 | 1.313 | 1.238 |
| r p95 | 2.844 | 1.925 |
| r p99 | 7.766 | 4.975 |
| share r>1.5 | 18.12% | 12.25% |
| share r>2 | 9.71% | 4.09% |
| share r>3 | 4.44% | 1.94% |
| share r>5 | 1.96% | 0.98% |
| acf lag 1 | 0.471 | 0.630 |
| acf lag 5 | 0.345 | 0.534 |
| acf lag 15 | 0.276 | 0.382 |
| corr(log r, log vol15) | 0.214 | 0.111 |

## Intraday shape (median r per 30-minute bucket)

| minutes | real data | simulator |
|---|---|---|
| 0-29 | 1.76 | 1.28 |
| 30-59 | 1.24 | 1.14 |
| 60-89 | 1.00 | 0.99 |
| 90-119 | 1.00 | 0.88 |
| 120-149 | 1.00 | 0.79 |
| 150-179 | 1.00 | 0.73 |
| 180-209 | 1.00 | 0.72 |
| 210-239 | 1.00 | 0.75 |
| 240-269 | 1.00 | 0.79 |
| 270-299 | 1.00 | 0.87 |
| 300-329 | 1.00 | 0.98 |
| 330-359 | 1.00 | 1.17 |
| 360-389 | 0.99 | 1.32 |
