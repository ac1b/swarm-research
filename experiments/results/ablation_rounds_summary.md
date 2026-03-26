# Round Scaling Experiment — game-ai

Config: full (3 agents + backtrack=3) | 3 runs per round count

| Rounds | Final (mean +/- std) | Delta % (mean +/- std) | Backtracks | Time (mean) |
|--------|----------------------|------------------------|------------|-------------|
| 2 | 67.71 +/- 7.81 | +164.3 +/- 30.5% | 0.0 | 434s |
| 4 | 85.42 +/- 15.02 | +233.4 +/- 58.6% | 0.0 | 729s |
| 8 | 91.25 +/- 7.60 | +256.2 +/- 29.7% | 1.3 | 1445s |
| 12 | 97.92 +/- 3.61 | +282.2 +/- 14.1% | 1.3 | 3059s |

## Per-run details

- rounds=2 | run 1 -> score=71.25 (705.0s)
- rounds=2 | run 2 -> score=58.75 (287.4s)
- rounds=2 | run 3 -> score=73.12 (308.4s)
- rounds=4 | run 1 -> score=86.25 (753.1s)
- rounds=4 | run 2 -> score=100.00 (846.9s)
- rounds=4 | run 3 -> score=70.00 (587.2s)
- rounds=8 | run 1 -> score=87.50 (1554.9s)
- rounds=8 | run 2 -> score=100.00 (1481.8s)
- rounds=8 | run 3 -> score=86.25 (1298.4s)
- rounds=12 | run 1 -> score=100.00 (3329.9s)
- rounds=12 | run 2 -> score=93.75 (3367.1s)
- rounds=12 | run 3 -> score=100.00 (2481.3s)
