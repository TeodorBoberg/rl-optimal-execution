# Stage 3 per-fold calibration

Each fold re-measured on its TRAINING days only (train = everything the walk-forward split does not hold out; the validation tail used for checkpoint selection is part of it, which is fine -- it precedes the test days). `full` = the same measurement on every day in the fold's file, i.e. what a single full-sample calibration gives.

## Fold 0

| parameter | config before | full sample | train only | train vs full |
|---|---:|---:|---:|---:|
| avg_spread_bps | 2.133 | 2.257 | 2.27354 | +0.7% |
| avg_daily_volume | 5000000 | 2.08829e+06 | 2.08796e+06 | -0.0% |
| volatility_per_min | 0.0003 | 0.00083176 | 0.000846664 | +1.8% |
| calm_vol | 0.000396 | 0.000371855 | 0.000386059 | +3.8% |
| volatile_vol | 0.001092 | 0.00129194 | 0.0013055 | +1.0% |
| prob_calm_to_volatile | 0.024138 | 0.0194395 | 0.019881 | +2.3% |
| prob_volatile_to_calm | 0.053132 | 0.0536359 | 0.0522601 | -2.6% |
| hawkes_decay | 0.0132 | 0.0573008 | 0.0564093 | -1.6% |
| volume ACF lag 1/5/15/30/60 (train) | | | 0.227 / 0.137 / 0.079 / 0.048 / 0.016 (fit amplitude 0.194) | |
| volume profile (total variation distance) | | | | 0.67% |
| regime method / calm share (train) | | | gmm / 0.71 | |

Per-ticker ADV, train-only vs full sample:

| ticker | full | train only | diff |
|---|---:|---:|---:|
| aapl | 2,292,232 | 2,275,799 | -0.7% |
| bac | 2,465,377 | 2,499,378 | +1.4% |
| cvx | 395,892 | 393,715 | -0.5% |
| googl | 1,686,175 | 1,613,660 | -4.3% |
| jpm | 409,739 | 435,234 | +6.2% |
| msft | 875,015 | 843,055 | -3.7% |
| nvda | 9,626,209 | 10,265,765 | +6.6% |
| pg | 327,707 | 335,342 | +2.3% |
| qqq | 1,587,224 | 1,586,736 | -0.0% |
| spy | 2,974,973 | 2,441,317 | -17.9% |
| tsla | 2,886,198 | 2,852,971 | -1.2% |
| wmt | 894,491 | 910,327 | +1.8% |
| xom | 726,574 | 690,208 | -5.0% |

## Fold 1

| parameter | config before | full sample | train only | train vs full |
|---|---:|---:|---:|---:|
| avg_spread_bps | 2.133 | 2.96963 | 2.257 | -24.0% |
| avg_daily_volume | 5000000 | 1.93712e+06 | 2.08829e+06 | +7.8% |
| volatility_per_min | 0.0003 | 0.000904615 | 0.00083176 | -8.1% |
| calm_vol | 0.000396 | 0.000370767 | 0.000371855 | +0.3% |
| volatile_vol | 0.001092 | 0.00133845 | 0.00129194 | -3.5% |
| prob_calm_to_volatile | 0.024138 | 0.0207907 | 0.0194395 | -6.5% |
| prob_volatile_to_calm | 0.053132 | 0.0529207 | 0.0536359 | +1.4% |
| hawkes_decay | 0.0132 | 0.0563782 | 0.0573008 | +1.6% |
| volume ACF lag 1/5/15/30/60 (train) | | | 0.220 / 0.134 / 0.076 / 0.044 / 0.015 (fit amplitude 0.190) | |
| volume profile (total variation distance) | | | | 0.45% |
| regime method / calm share (train) | | | gmm / 0.72 | |

Per-ticker ADV, train-only vs full sample:

| ticker | full | train only | diff |
|---|---:|---:|---:|
| aapl | 2,166,423 | 2,292,232 | +5.8% |
| bac | 2,381,827 | 2,465,377 | +3.5% |
| cvx | 368,223 | 395,892 | +7.5% |
| googl | 1,599,449 | 1,686,175 | +5.4% |
| jpm | 375,385 | 409,739 | +9.2% |
| msft | 815,591 | 875,015 | +7.3% |
| nvda | 8,650,978 | 9,626,209 | +11.3% |
| pg | 315,413 | 327,707 | +3.9% |
| qqq | 1,532,044 | 1,587,224 | +3.6% |
| spy | 2,774,716 | 2,974,973 | +7.2% |
| tsla | 2,641,020 | 2,886,198 | +9.3% |
| wmt | 859,916 | 894,491 | +4.0% |
| xom | 701,636 | 726,574 | +3.6% |

## Fold 2

| parameter | config before | full sample | train only | train vs full |
|---|---:|---:|---:|---:|
| avg_spread_bps | 2.133 | 3.46968 | 2.96963 | -14.4% |
| avg_daily_volume | 5000000 | 1.8484e+06 | 1.93712e+06 | +4.8% |
| volatility_per_min | 0.0003 | 0.000925092 | 0.000904615 | -2.2% |
| calm_vol | 0.000396 | 0.000378055 | 0.000370767 | -1.9% |
| volatile_vol | 0.001092 | 0.00136675 | 0.00133845 | -2.1% |
| prob_calm_to_volatile | 0.024138 | 0.0210887 | 0.0207907 | -1.4% |
| prob_volatile_to_calm | 0.053132 | 0.0529069 | 0.0529207 | +0.0% |
| hawkes_decay | 0.0132 | 0.0569165 | 0.0563782 | -0.9% |
| volume ACF lag 1/5/15/30/60 (train) | | | 0.215 / 0.131 / 0.077 / 0.044 / 0.017 (fit amplitude 0.185) | |
| volume profile (total variation distance) | | | | 0.33% |
| regime method / calm share (train) | | | gmm / 0.70 | |

Per-ticker ADV, train-only vs full sample:

| ticker | full | train only | diff |
|---|---:|---:|---:|
| aapl | 2,061,350 | 2,166,423 | +5.1% |
| bac | 2,369,063 | 2,381,827 | +0.5% |
| cvx | 365,313 | 368,223 | +0.8% |
| googl | 1,538,327 | 1,599,449 | +4.0% |
| jpm | 359,759 | 375,385 | +4.3% |
| msft | 828,661 | 815,591 | -1.6% |
| nvda | 7,993,301 | 8,650,978 | +8.2% |
| pg | 325,326 | 315,413 | -3.0% |
| qqq | 1,490,723 | 1,532,044 | +2.8% |
| spy | 2,651,343 | 2,774,716 | +4.7% |
| tsla | 2,407,013 | 2,641,020 | +9.7% |
| wmt | 907,704 | 859,916 | -5.3% |
| xom | 731,277 | 701,636 | -4.1% |

## Fold 3

| parameter | config before | full sample | train only | train vs full |
|---|---:|---:|---:|---:|
| avg_spread_bps | 2.133 | 3.8566 | 3.46968 | -10.0% |
| avg_daily_volume | 5000000 | 1.77692e+06 | 1.8484e+06 | +4.0% |
| volatility_per_min | 0.0003 | 0.000935508 | 0.000925092 | -1.1% |
| calm_vol | 0.000396 | 0.000381341 | 0.000378055 | -0.9% |
| volatile_vol | 0.001092 | 0.00134192 | 0.00136675 | +1.8% |
| prob_calm_to_volatile | 0.024138 | 0.0231758 | 0.0210887 | -9.0% |
| prob_volatile_to_calm | 0.053132 | 0.0529439 | 0.0529069 | -0.1% |
| hawkes_decay | 0.0132 | 0.0579674 | 0.0569165 | -1.8% |
| volume ACF lag 1/5/15/30/60 (train) | | | 0.219 / 0.133 / 0.078 / 0.044 / 0.017 (fit amplitude 0.188) | |
| volume profile (total variation distance) | | | | 0.32% |
| regime method / calm share (train) | | | gmm / 0.70 | |

Per-ticker ADV, train-only vs full sample:

| ticker | full | train only | diff |
|---|---:|---:|---:|
| aapl | 1,944,606 | 2,061,350 | +6.0% |
| bac | 2,332,740 | 2,369,063 | +1.6% |
| cvx | 373,290 | 365,313 | -2.1% |
| googl | 1,453,377 | 1,538,327 | +5.8% |
| jpm | 344,568 | 359,759 | +4.4% |
| msft | 843,536 | 828,661 | -1.8% |
| nvda | 7,602,060 | 7,993,301 | +5.1% |
| pg | 333,144 | 325,326 | -2.3% |
| qqq | 1,471,628 | 1,490,723 | +1.3% |
| spy | 2,558,301 | 2,651,343 | +3.6% |
| tsla | 2,226,754 | 2,407,013 | +8.1% |
| wmt | 870,605 | 907,704 | +4.3% |
| xom | 745,405 | 731,277 | -1.9% |

## Unseen-ticker groups (fold 3)

- group 0: aapl, jpm, qqq, xom  ->  configs\stage3b_unseen/g0_train.yaml (without them), configs\stage3b_unseen/g0_eval.yaml (only them)
- group 1: bac, msft, spy  ->  configs\stage3b_unseen/g1_train.yaml (without them), configs\stage3b_unseen/g1_eval.yaml (only them)
- group 2: cvx, nvda, tsla  ->  configs\stage3b_unseen/g2_train.yaml (without them), configs\stage3b_unseen/g2_eval.yaml (only them)
- group 3: googl, pg, wmt  ->  configs\stage3b_unseen/g3_train.yaml (without them), configs\stage3b_unseen/g3_eval.yaml (only them)
