"""Evaluate TSP solver: total tour distance (lower = better)."""
import random
import sys
import time

sys.path.insert(0, "target")

random.seed(42)
N = 40
cities = [(random.uniform(0, 100), random.uniform(0, 100)) for _ in range(N)]

start = time.perf_counter()
try:
    from solver import solve
    route = solve(cities)
except Exception as e:
    print("SCORE: 99999", flush=True)
    sys.exit(0)

elapsed = time.perf_counter() - start

# Timeout penalty
if elapsed > 25:
    print("SCORE: 99999", flush=True)
    sys.exit(0)

# Validate: must be a valid permutation of 0..N-1
try:
    if sorted(route) != list(range(N)):
        print("SCORE: 99999", flush=True)
        sys.exit(0)
except (TypeError, ValueError):
    print("SCORE: 99999", flush=True)
    sys.exit(0)

# Compute total distance
try:
    from moves import route_distance
    total = route_distance(route, cities)
except Exception:
    print("SCORE: 99999", flush=True)
    sys.exit(0)

print(f"SCORE: {total:.2f}", flush=True)
