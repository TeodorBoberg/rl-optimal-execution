# Training throughput benchmark

Config `configs\stage3\fold0.yaml`, 40,000 steps per run, CPU logical processors 12, CUDA yes.

| device | simulator workers (n_envs) | torch threads | eval | runs at once | steps/s per run | total steps/s | collect | update | eval | 12 x 10M models |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| cpu | 8 | 6 | on | 1 | 2,922 | 2,922 | 79% | 21% | 0% | 11.4 h |
| cpu | 8 | 6 | off | 1 | 2,926 | 2,926 | 79% | 21% | 0% | 11.4 h |
| cuda | 8 | 6 | off | 1 | 1,664 | 1,664 | 80% | 20% | 0% | 20.0 h |
| cpu | 8 | 1 | off | 1 | 2,175 | 2,175 | 66% | 34% | 0% | 15.3 h |
| cpu | 8 | 1 | off | 2 | 1,728 | 3,456 | 68% | 32% | 0% | 9.6 h |
| cpu | 8 | 1 | off | 3 | 1,374 | 4,123 | 71% | 29% | 0% | 8.1 h |
| cpu | 8 | 1 | off | 4 | 1,071 | 4,283 | 75% | 25% | 0% | 7.8 h |
| cpu | 8 | 1 | on | 3 | 1,422 | 4,265 | 71% | 29% | 0% | 7.8 h |

collect = simulating the market for new experience; update = PPO gradient steps; eval = the checkpoint-selection evaluation (single environment). Shares are of each run's wall time, averaged. '12 x 10M models' = hours to train all walk-forward models at the total rate (ignores start-up).
