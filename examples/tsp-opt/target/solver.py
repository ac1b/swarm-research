"""TSP solver. Optimize to find the shortest tour."""
import random
from config import MAX_ITERATIONS, TEMPERATURE, COOLING_RATE
from moves import dist, route_distance, swap_move


def solve(cities):
    """Find a short tour visiting all cities. Returns list of city indices."""
    n = len(cities)

    # Greedy nearest-neighbor construction
    visited = [False] * n
    route = [0]
    visited[0] = True
    for _ in range(n - 1):
        last = route[-1]
        best_next = -1
        best_d = float("inf")
        for j in range(n):
            if not visited[j]:
                d = dist(cities, last, j)
                if d < best_d:
                    best_d = d
                    best_next = j
        route.append(best_next)
        visited[best_next] = True

    # Simple random swap improvement
    rng = random.Random(0)
    best_dist = route_distance(route, cities)
    for _ in range(MAX_ITERATIONS):
        i = rng.randint(0, n - 1)
        j = rng.randint(0, n - 1)
        if i == j:
            continue
        new_route, delta = swap_move(route, cities, i, j)
        if delta < 0:
            route = new_route
            best_dist += delta

    return route
