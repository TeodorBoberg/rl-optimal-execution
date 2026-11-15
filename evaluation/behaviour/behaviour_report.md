# What did the agent learn?

Agent `s3` with guardrail 0.05,10, folds 0,1,2,3, seeds 42,43,44, urgencies 0.25,0.5,0.75, 40 episodes per side per fold. Benchmarks run on the same episodes.

## 1. Where the cost goes (bps of the order, mean over episodes)

Execution = half-spread paid + impact. Spread capture = volume-weighted spread paid / time-weighted spread over the day (< 1: trades more when the spread is narrow).

| urgency | strategy | execution | half-spread | impact | spread capture | participation |
|---|---|---:|---:|---:|---:|---:|
| 0.25 | rl | 3.86 | 2.44 | 1.41 | 1.112 | 0.100 |
| 0.5 | rl | 4.12 | 2.46 | 1.66 | 1.211 | 0.137 |
| 0.75 | rl | 4.52 | 2.56 | 1.96 | 1.298 | 0.185 |
| - | ac@0.05 | 4.17 | 2.75 | 1.42 | 1.151 | 0.072 |
| - | acl@0.05 | 4.59 | 3.13 | 1.47 | 1.317 | 0.073 |
| - | acs1@0.05 | 4.91 | 3.01 | 1.90 | 1.322 | 0.075 |
| - | gacs1@0.05 | 4.91 | 3.01 | 1.90 | 1.322 | 0.075 |
| - | twap | 3.49 | 2.36 | 1.13 | 0.997 | 0.072 |

## 2. What `rl` reacts to: pace vs an even pace over the time left, by decile of each input (all urgencies pooled)

1.0 = trades exactly the even pace; 2.0 = twice as fast. Read across a row: if pace changes a lot from the lowest to the highest decile, the strategy reacts to that input.

| input | d1 | d2 | d3 | d4 | d5 | d6 | d7 | d8 | d9 | d10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| spread / mean spread so far in the order | 1.24 (0.18) | 2.42 (0.33) | 2.63 (0.45) | 2.62 (0.57) | 2.46 (0.68) | 2.37 (0.82) | 2.43 (0.94) | 3.38 (1) | 1.11 (1.1) | 0.58 (1.6) |
| last minute's volume / normal | 0.99 (0.099) | 1.36 (0.2) | 1.64 (0.28) | 1.86 (0.37) | 2.13 (0.47) | 2.39 (0.59) | 2.69 (0.74) | 3.07 (0.96) | 3.51 (1.3) | 4.21 (2.3) |
| price move against the order since arrival (bps) | 1.33 (-2.2e+02) | 2.20 (-89) | 2.21 (-46) | 2.50 (-18) | 2.69 (-0.27) | 2.42 (15) | 2.36 (35) | 2.13 (64) | 2.09 (1.1e+02) | 1.53 (1.9e+02) |
| recent volatility / calibrated | 2.68 (0.2) | 2.72 (0.31) | 2.45 (0.4) | 2.30 (0.49) | 2.25 (0.58) | 2.08 (0.7) | 2.03 (0.86) | 2.02 (1.1) | 1.40 (1.4) | 0.93 (2.3) |
| fraction of the day elapsed | 4.40 (0.027) | 3.92 (0.082) | 3.21 (0.14) | 2.68 (0.19) | 2.23 (0.26) | 1.91 (0.33) | 1.61 (0.41) | 1.39 (0.51) | 1.23 (0.62) | 0.80 (0.8) |
| share of order ahead of a straight-line pace | 0.81 (-0.076) | 0.70 (-0.0051) | 1.58 (0.084) | 1.89 (0.16) | 2.00 (0.23) | 2.17 (0.29) | 2.44 (0.35) | 2.97 (0.42) | 4.35 (0.5) | 9.04 (0.62) |

Cells: median pace (median input value in that decile). Minutes after the order is 98% done are left out.

## 2. What `acs1@0.05` reacts to: pace vs an even pace over the time left, by decile of each input (all urgencies pooled)

1.0 = trades exactly the even pace; 2.0 = twice as fast. Read across a row: if pace changes a lot from the lowest to the highest decile, the strategy reacts to that input.

| input | d1 | d2 | d3 | d4 | d5 | d6 | d7 | d8 | d9 | d10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| spread / mean spread so far in the order | 4.00 (0.27) | 2.50 (0.44) | 1.81 (0.57) | 1.33 (0.68) | 1.42 (0.82) | 1.08 (0.93) | 0.91 (0.98) | 0.93 (1) | 1.50 (1) | 0.58 (1.4) |
| last minute's volume / normal | 0.58 (0.1) | 0.74 (0.2) | 0.89 (0.27) | 1.04 (0.35) | 1.23 (0.44) | 1.42 (0.55) | 1.72 (0.69) | 2.22 (0.89) | 2.81 (1.2) | 5.04 (2.2) |
| price move against the order since arrival (bps) | 1.57 (-1.7e+02) | 1.30 (-71) | 1.24 (-39) | 1.56 (-16) | 1.53 (0.6) | 1.44 (17) | 1.36 (36) | 1.45 (64) | 1.27 (1e+02) | 1.19 (1.8e+02) |
| recent volatility / calibrated | 0.74 (0.14) | 0.95 (0.23) | 1.06 (0.3) | 1.13 (0.37) | 1.17 (0.44) | 1.40 (0.53) | 1.53 (0.64) | 1.92 (0.81) | 2.75 (1.1) | 3.52 (1.9) |
| fraction of the day elapsed | 4.78 (0.038) | 3.32 (0.12) | 2.65 (0.2) | 2.15 (0.28) | 1.57 (0.37) | 1.17 (0.46) | 0.89 (0.55) | 0.77 (0.65) | 0.61 (0.76) | 0.45 (0.89) |
| share of order ahead of a straight-line pace | 0.52 (0.021) | 0.75 (0.099) | 0.92 (0.16) | 1.04 (0.22) | 1.22 (0.27) | 1.33 (0.31) | 1.57 (0.36) | 1.87 (0.42) | 2.40 (0.49) | 4.13 (0.6) |

Cells: median pace (median input value in that decile). Minutes after the order is 98% done are left out.

## 2. What `gacs1@0.05` reacts to: pace vs an even pace over the time left, by decile of each input (all urgencies pooled)

1.0 = trades exactly the even pace; 2.0 = twice as fast. Read across a row: if pace changes a lot from the lowest to the highest decile, the strategy reacts to that input.

| input | d1 | d2 | d3 | d4 | d5 | d6 | d7 | d8 | d9 | d10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| spread / mean spread so far in the order | 4.00 (0.27) | 2.50 (0.44) | 1.81 (0.57) | 1.33 (0.68) | 1.42 (0.82) | 1.08 (0.93) | 0.91 (0.98) | 0.93 (1) | 1.50 (1) | 0.58 (1.4) |
| last minute's volume / normal | 0.59 (0.1) | 0.74 (0.2) | 0.89 (0.27) | 1.04 (0.35) | 1.23 (0.44) | 1.42 (0.55) | 1.72 (0.69) | 2.22 (0.89) | 2.81 (1.2) | 5.04 (2.2) |
| price move against the order since arrival (bps) | 1.57 (-1.7e+02) | 1.30 (-71) | 1.24 (-39) | 1.56 (-16) | 1.53 (0.6) | 1.44 (17) | 1.36 (36) | 1.45 (64) | 1.27 (1e+02) | 1.19 (1.8e+02) |
| recent volatility / calibrated | 0.74 (0.14) | 0.95 (0.23) | 1.06 (0.3) | 1.13 (0.37) | 1.17 (0.44) | 1.40 (0.53) | 1.53 (0.64) | 1.92 (0.81) | 2.75 (1.1) | 3.52 (1.9) |
| fraction of the day elapsed | 4.78 (0.038) | 3.32 (0.12) | 2.65 (0.2) | 2.15 (0.28) | 1.57 (0.37) | 1.17 (0.46) | 0.89 (0.55) | 0.77 (0.65) | 0.61 (0.76) | 0.46 (0.89) |
| share of order ahead of a straight-line pace | 0.53 (0.021) | 0.75 (0.099) | 0.92 (0.16) | 1.04 (0.22) | 1.22 (0.27) | 1.33 (0.31) | 1.57 (0.36) | 1.87 (0.42) | 2.40 (0.49) | 4.13 (0.6) |

Cells: median pace (median input value in that decile). Minutes after the order is 98% done are left out.

## 3. How much of the agent is a simple rule?

log(pace) regressed on the six inputs (standardised), 612,883 agent-minutes.

| input | coefficient (per 1 sd) |
|---|---:|
| intercept | +0.651 |
| spread / mean spread so far in the order | -0.363 |
| last minute's volume / normal | +0.147 |
| price move against the order since arrival (bps) | -0.014 |
| recent volatility / calibrated | -0.169 |
| fraction of the day elapsed | -0.221 |
| share of order ahead of a straight-line pace | +0.608 |

Linear R^2 = 0.420; depth-3 tree R^2 = 0.408.

Depth-3 tree (log pace; 0 = even pace, +0.69 = twice as fast, -0.69 = half):

```
|--- ahead <= 0.12
|   |--- ahead <= -0.00
|   |   |--- time_frac <= 0.06
|   |   |   |--- value: [-1.88]
|   |   |--- time_frac >  0.06
|   |   |   |--- value: [-0.47]
|   |--- ahead >  -0.00
|   |   |--- time_frac <= 0.11
|   |   |   |--- value: [1.09]
|   |   |--- time_frac >  0.11
|   |   |   |--- value: [-0.30]
|--- ahead >  0.12
|   |--- ahead <= 0.48
|   |   |--- rel_spread <= 1.40
|   |   |   |--- value: [0.86]
|   |   |--- rel_spread >  1.40
|   |   |   |--- value: [-1.04]
|   |--- ahead >  0.48
|   |   |--- ahead <= 0.61
|   |   |   |--- value: [1.55]
|   |   |--- ahead >  0.61
|   |   |   |--- value: [2.28]

```
