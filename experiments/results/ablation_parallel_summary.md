# Parallel vs Sequential — game-ai

Rounds: 6 | Runs: 3 | Config: full (3 agents + backtrack=3)

| Mode | Final (mean +/- std) | Delta % | Time (mean) |
|------|----------------------|---------|-------------|
| sequential | 81.67 +/- 6.88 | +218.8 +/- 26.9% | 1122s |
| parallel | 81.46 +/- 6.26 | +218.0 +/- 24.4% | 429s |

## Per-run details

- sequential | run 1 -> score=86.25 (1349.0s)
- sequential | run 2 -> score=85.00 (945.2s)
- sequential | run 3 -> score=73.75 (1071.7s)
- parallel | run 1 -> score=87.50 (426.5s)
- parallel | run 2 -> score=75.00 (396.0s)
- parallel | run 3 -> score=81.88 (465.4s)
