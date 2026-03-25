"""Move operators for TSP local search."""
import math


def dist(cities, i, j):
    """Euclidean distance between two cities."""
    x1, y1 = cities[i]
    x2, y2 = cities[j]
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def route_distance(route, cities):
    """Total tour distance."""
    total = 0.0
    n = len(route)
    for i in range(n):
        total += dist(cities, route[i], route[(i + 1) % n])
    return total


def swap_move(route, cities, i, j):
    """Swap cities at positions i and j. Returns (new_route, delta)."""
    new_route = route[:]
    new_route[i], new_route[j] = new_route[j], new_route[i]
    old_dist = route_distance(route, cities)
    new_dist = route_distance(new_route, cities)
    return new_route, new_dist - old_dist
