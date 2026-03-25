---
target: target/packer.py
eval: python3 eval.py
direction: maximize
rounds: 10
backtrack: 3
max_backtracks: 3
timeout: 30
---
Optimize the bin packing algorithm in `pack()` for minimum bin usage.

**Goal:** Pack items into as few bins as possible (each bin has capacity 1.0).

**Rules:**
- Every item must appear exactly once across all bins
- No bin may exceed capacity 1.0
- Input: list of floats (0 < size <= 1.0), output: list of bins (each a list of floats)
- Python stdlib only, no numpy/scipy
- Function signature must stay: `pack(items, bin_capacity=1.0) -> list[list[float]]`

**Scoring:** avg(lower_bound / actual_bins) * 100 across 8 test cases. Perfect = 100.

**Approaches to explore:** First-Fit Decreasing, Best-Fit Decreasing, hybrid heuristics, item sorting strategies.
