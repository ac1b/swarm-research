"""Evaluate sorting speed and correctness."""
import random
import sys
import time

sys.path.insert(0, "target")
try:
    from sorter import sort
except Exception as e:
    print(f"Import error: {e}", file=sys.stderr)
    print("SCORE: 0", flush=True)
    sys.exit(0)

random.seed(42)

# Correctness check
for size in [10, 100, 500]:
    data = [random.randint(-10000, 10000) for _ in range(size)]
    try:
        result = sort(data)
    except Exception:
        print("SCORE: 0", flush=True)
        sys.exit(0)
    expected = sorted(data)
    if result != expected:
        print("SCORE: 0", flush=True)
        sys.exit(0)

# Speed benchmark
data = [random.randint(-10000, 10000) for _ in range(2000)]
runs = 5
times = []
for _ in range(runs):
    start = time.perf_counter()
    try:
        sort(list(data))
    except Exception:
        print("SCORE: 0", flush=True)
        sys.exit(0)
    elapsed = time.perf_counter() - start
    times.append(elapsed)

median_time = sorted(times)[len(times) // 2]
ops_per_sec = 1.0 / median_time if median_time > 0 else 0
print(f"SCORE: {ops_per_sec:.2f}", flush=True)
