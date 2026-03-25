---
target: [target/sorter.py, target/config.py]
eval: python3 eval.py
direction: maximize
rounds: 5
timeout: 30
---

Optimize the sorting implementation for maximum speed (operations per second).

Two files work together:
- `target/sorter.py` — the sorting algorithm (currently naive bubble sort)
- `target/config.py` — parameters like THRESHOLD and CHUNK_SIZE

You may modify either or both files. The algorithm MUST return correctly sorted output.
Use only Python standard library. Keep the function signature: `def sort(data) -> list`.
