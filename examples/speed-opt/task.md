---
target: target/solution.py
eval: python3 eval.py
direction: maximize
rounds: 5
timeout: 30
---

Optimize the Python function `process_data` for maximum speed.

The function takes a list of numbers and must return the correct result.
Correctness is verified by the eval script — if the output is wrong, score = 0.

You may use any Python standard library. NumPy is NOT available.
Keep the function signature: `def process_data(data: list) -> float`
