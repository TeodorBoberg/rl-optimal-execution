# Training throughput benchmark

Config `configs\stage3\fold0.yaml`, 150,000 steps per run, CPU logical processors 12, CUDA yes.

| device | simulator workers (n_envs) | torch threads | eval | runs at once | steps/s per run | total steps/s | collect | update | eval | 12 x 10M models |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| cpu | 8 | 6 | on | 1 | 1,874 | 1,874 | 56% | 16% | 28% | 17.8 h |
| cpu | 8 | 6 | off | 1 | 2,617 | 2,617 | 78% | 22% | 0% | 12.7 h |
| cpu | 8 | 1 | on | 3 | 1,333 | 3,998 | 53% | 25% | 22% | 8.3 h |
| cpu | 8 | 2 | on | 3 | 1,326 | 3,977 | 61% | 17% | 21% | 8.4 h |

collect = simulating the market for new experience; update = PPO gradient steps; eval = the checkpoint-selection evaluation (single environment). Shares are of each run's wall time, averaged. '12 x 10M models' = hours to train all walk-forward models at the total rate (ignores start-up).
