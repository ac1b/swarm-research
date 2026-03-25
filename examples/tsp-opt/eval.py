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
    print(f"SCORE: 99999")
    sys.exit(0)

elapsed = time.perf_counter() - start

# Timeout penalty
if elapsed > 25:
    print(f"SCORE: 99999")
    sys.exit(0)

# Validate: must be a valid permutation of 0..N-1
if sorted(route) != list(range(N)):
    print(f"SCORE: 99999")
    sys.exit(0)

# Compute total distance
from moves import route_distance
total = route_distance(route, cities)

print(f"SCORE: {total:.2f}")
