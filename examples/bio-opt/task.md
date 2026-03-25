---
target: target/finder.py
eval: python3 eval.py
direction: maximize
rounds: 10
backtrack: 3
max_backtracks: 3
timeout: 30
---
Implement a DNA motif finder — the planted motif search problem.

**Problem:** Given N DNA sequences (alphabet ACGT), each containing a hidden motif
of length k (possibly with a few mutations), find the consensus motif.

**Goal:** Maximize similarity between found motif and the true planted motif.

**Rules:**
- Function signature: `find_motif(sequences: list[str], k: int) -> str`
- Return a string of length k using only characters A, C, G, T
- Python stdlib only, no biopython/numpy
- Must handle varying sequence lengths, mutation levels, and motif sizes

**Scoring:** Average Hamming similarity to true motif across 6 test cases * 100.
Random guessing = ~25. Perfect recovery = 100.

**Approaches to explore:** Profile matrices, greedy motif search, Gibbs sampling,
expectation maximization, consensus scoring with position weight matrices.
