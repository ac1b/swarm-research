---
target: [target/solver.py, target/moves.py, target/config.py]
eval: python3 eval.py
direction: minimize
rounds: 8
timeout: 30
backtrack: 3
max_backtracks: 2
---

Minimize total tour distance for a 40-city Traveling Salesman Problem.

Three files work together:
- `target/solver.py` — main solve(cities) function. Currently: nearest-neighbor + random swaps.
- `target/moves.py` — move operators and distance helpers. Currently: only naive swap (recomputes full distance).
- `target/config.py` — parameters: MAX_ITERATIONS, TEMPERATURE, COOLING_RATE.

Improvement directions:
- Better local search: 2-opt, or-opt, simulated annealing, Lin-Kernighan style moves.
- Efficient delta computation in moves (don't recompute full tour distance).
- Better construction heuristic (e.g. christofides-like, greedy edge insertion).
- Parameter tuning (more iterations, proper cooling schedule).

Constraints:
- Must return a valid permutation of 0..N-1.
- Timeout: 25 seconds. Don't run forever.
- Python standard library only (no numpy/scipy).
- Keep function signature: `def solve(cities) -> list` where cities is list of (x,y) tuples.
