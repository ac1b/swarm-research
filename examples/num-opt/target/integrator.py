import math


def integrate(f, a: float, b: float, n_points: int) -> float:
    """Compute the definite integral of f from a to b.

    Args:
        f: callable, function to integrate (takes float, returns float)
        a: lower bound
        b: upper bound
        n_points: max number of function evaluations allowed

    Returns:
        approximate integral value
    """
    # Left Riemann sum (naive)
    h = (b - a) / n_points
    total = 0.0
    for i in range(n_points):
        x = a + i * h
        total += f(x)
    return total * h
