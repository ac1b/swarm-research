# Scheduler Ablation Results

Rounds: 6 | Runs: 3

| Config | Baseline | Final (mean +/- std) | Delta % | Backtracks |
|--------|----------|----------------------|---------|------------|
| full | 213837 | 97750 +/- 33066 | -54.3 +/- 15.5% | 0.3 |
| no_backtrack | 213837 | 71094 +/- 22087 | -66.8 +/- 10.3% | 0.0 |
| single_agent | 213837 | 84063 +/- 11075 | -60.7 +/- 5.2% | 0.7 |

## Per-run details

- full | run 1 -> score=133251 (500.4s)
- full | run 2 -> score=67830 (839.9s)
- full | run 3 -> score=92168 (596.0s)
- no_backtrack | run 1 -> score=46210 (742.0s)
- no_backtrack | run 2 -> score=88375 (814.4s)
- no_backtrack | run 3 -> score=78696 (787.3s)
- single_agent | run 1 -> score=71781 (363.9s)
- single_agent | run 2 -> score=93289 (212.0s)
- single_agent | run 3 -> score=87119 (361.0s)
