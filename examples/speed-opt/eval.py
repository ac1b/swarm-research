"""Eval script: measures speed of process_data while verifying correctness."""

import importlib
import math
import random
import sys
import time

# Generate deterministic test data
random.seed(42)
DATA_SMALL = [random.uniform(-100, 100) for _ in range(10_000)]
DATA_LARGE = [random.uniform(-100, 100) for _ in range(200_000)]

# Pre-compute correct answers with the reference implementation
def reference(data):
    result = 0.0
    for x in data:
        if x > 0:
            val = x ** 0.5
            if val > 1.0:
                result += val * 2.0 + 1.0 / (val + 1.0)
            else:
                result += val
    return round(result, 6)

EXPECTED_SMALL = reference(DATA_SMALL)
EXPECTED_LARGE = reference(DATA_LARGE)


def load_solution():
    """Import/reload the solution module."""
    if "target.solution" in sys.modules:
        return importlib.reload(sys.modules["target.solution"])
    return importlib.import_module("target.solution")


def check_correctness(mod):
    """Verify the solution returns correct results."""
    r1 = mod.process_data(DATA_SMALL)
    r2 = mod.process_data(DATA_LARGE)
    if not math.isclose(r1, EXPECTED_SMALL, rel_tol=1e-4):
        print(f"WRONG on small: got {r1}, expected {EXPECTED_SMALL}", file=sys.stderr)
        return False
    if not math.isclose(r2, EXPECTED_LARGE, rel_tol=1e-4):
        print(f"WRONG on large: got {r2}, expected {EXPECTED_LARGE}", file=sys.stderr)
        return False
    return True


def benchmark(mod, iterations=20):
    """Benchmark and return operations per second."""
    # Warmup
    mod.process_data(DATA_SMALL)

    start = time.perf_counter()
    for _ in range(iterations):
        mod.process_data(DATA_LARGE)
    elapsed = time.perf_counter() - start

    return iterations / elapsed  # ops/sec


def main():
    try:
        mod = load_solution()
    except Exception as e:
        print(f"Import error: {e}", file=sys.stderr)
        print("SCORE: 0.0", flush=True)
        return

    if not check_correctness(mod):
        print("SCORE: 0.0", flush=True)
        return

    score = benchmark(mod)
    print(f"SCORE: {score:.4f}", flush=True)


if __name__ == "__main__":
    main()
