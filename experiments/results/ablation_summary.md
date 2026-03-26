# Ablation Experiment Results

Rounds per run: 6 | Runs per config: 3

| Example | Config | Baseline | Final (mean +/- std) | Delta % (mean +/- std) | Backtracks |
|---------|--------|----------|----------------------|------------------------|------------|
| tsp-opt | full | 592.71 | 494.80 +/- 2.48 | -16.5 +/- 0.4% | 0.7 |
| tsp-opt | no_backtrack | 592.71 | 497.55 +/- 4.53 | -16.1 +/- 0.8% | 0.0 |
| tsp-opt | single_agent | 592.71 | 495.61 +/- 0.45 | -16.4 +/- 0.1% | 0.3 |
| game-ai | full | 25.62 | 91.67 +/- 14.43 | +257.8 +/- 56.3% | 0.3 |
| game-ai | no_backtrack | 25.62 | 74.17 +/- 0.72 | +189.5 +/- 2.8% | 0.0 |
| game-ai | single_agent | 25.62 | 77.71 +/- 7.56 | +203.3 +/- 29.5% | 0.0 |
| bio-opt | full | 39.58 | 49.91 +/- 6.20 | +26.1 +/- 15.7% | 0.7 |
| bio-opt | no_backtrack | 39.58 | 45.32 +/- 5.95 | +14.5 +/- 15.0% | 0.0 |
| bio-opt | single_agent | 39.58 | 43.24 +/- 3.21 | +9.2 +/- 8.1% | 0.7 |

## Per-run details

- tsp-opt | full | run 1 -> score=493.37 (562.0s)
- tsp-opt | full | run 2 -> score=497.66 (566.5s)
- tsp-opt | full | run 3 -> score=493.37 (1038.6s)
- tsp-opt | no_backtrack | run 1 -> score=493.37 (861.7s)
- tsp-opt | no_backtrack | run 2 -> score=502.36 (826.6s)
- tsp-opt | no_backtrack | run 3 -> score=496.91 (1459.7s)
- tsp-opt | single_agent | run 1 -> score=496.13 (181.5s)
- tsp-opt | single_agent | run 2 -> score=495.35 (268.8s)
- tsp-opt | single_agent | run 3 -> score=495.35 (443.0s)
- game-ai | full | run 1 -> score=75.00 (1615.6s)
- game-ai | full | run 2 -> score=100.00 (2029.1s)
- game-ai | full | run 3 -> score=100.00 (1260.7s)
- game-ai | no_backtrack | run 1 -> score=73.75 (1694.8s)
- game-ai | no_backtrack | run 2 -> score=73.75 (877.7s)
- game-ai | no_backtrack | run 3 -> score=75.00 (1277.3s)
- game-ai | single_agent | run 1 -> score=75.00 (350.2s)
- game-ai | single_agent | run 2 -> score=71.88 (377.1s)
- game-ai | single_agent | run 3 -> score=86.25 (712.5s)
- bio-opt | full | run 1 -> score=42.78 (773.5s)
- bio-opt | full | run 2 -> score=54.03 (1146.4s)
- bio-opt | full | run 3 -> score=52.92 (643.5s)
- bio-opt | no_backtrack | run 1 -> score=39.86 (987.1s)
- bio-opt | no_backtrack | run 2 -> score=44.44 (845.2s)
- bio-opt | no_backtrack | run 3 -> score=51.67 (1069.7s)
- bio-opt | single_agent | run 1 -> score=39.58 (290.3s)
- bio-opt | single_agent | run 2 -> score=44.58 (281.0s)
- bio-opt | single_agent | run 3 -> score=45.56 (254.9s)
