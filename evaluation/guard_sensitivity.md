# Guardrail sensitivity

Gap to the best classical strategy at equal risk (bps, negative = agent cheaper), mean over the runs (fold x seed), with the day-bootstrap 95% interval. `runs < 0` = how many of the runs beat the best classical strategy. Same models and episodes in every column; only the guardrail differs. The classical strategies are the unguarded ones in every column.

| urgency | none | 2.5%,10 | 5%,10 | 10%,10 | 5%,5 | 5%,30 |
|---|---|---|---|---|---|---|
| 0 | +6.19 [+4.92, +7.61], runs<0: 0/12 | -0.19 [-0.26, -0.13], runs<0: 10/12 | -0.06 [-0.14, +0.01], runs<0: 6/12 | +0.27 [+0.15, +0.38], runs<0: 4/12 | -0.13 [-0.20, -0.06], runs<0: 7/12 | +0.30 [+0.18, +0.42], runs<0: 3/12 |
| 0.25 | +2.92 [+2.05, +3.89], runs<0: 5/12 | -0.32 [-0.41, -0.22], runs<0: 12/12 | -0.24 [-0.33, -0.14], runs<0: 9/12 | -0.05 [-0.17, +0.07], runs<0: 7/12 | -0.28 [-0.37, -0.18], runs<0: 11/12 | -0.04 [-0.16, +0.09], runs<0: 7/12 |
| 0.5 | +1.32 [+0.75, +1.88], runs<0: 5/12 | -0.30 [-0.45, -0.18], runs<0: 11/12 | -0.26 [-0.41, -0.14], runs<0: 11/12 | -0.16 [-0.33, -0.03], runs<0: 8/12 | -0.28 [-0.43, -0.16], runs<0: 11/12 | -0.15 [-0.32, -0.02], runs<0: 8/12 |
| 0.75 | +0.53 [+0.12, +0.88], runs<0: 6/12 | -0.24 [-0.39, -0.06], runs<0: 8/12 | -0.21 [-0.37, -0.04], runs<0: 9/12 | -0.16 [-0.33, +0.02], runs<0: 8/12 | -0.22 [-0.38, -0.05], runs<0: 9/12 | -0.15 [-0.33, +0.03], runs<0: 8/12 |
| 1 | +0.17 [-0.14, +0.48], runs<0: 5/12 | -0.17 [-0.31, +0.01], runs<0: 7/12 | -0.16 [-0.31, +0.01], runs<0: 7/12 | -0.15 [-0.30, +0.04], runs<0: 7/12 | -0.16 [-0.31, +0.01], runs<0: 7/12 | -0.14 [-0.30, +0.05], runs<0: 7/12 |

Worst single run (largest gap at any urgency): none: +21.35, 2.5%,10: +0.23, 5%,10: +0.29, 10%,10: +0.86, 5%,5: +0.23, 5%,30: +0.91
