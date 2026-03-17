import math

def process_data(data: list) -> float:
    """Process a list of numbers: filter, transform, aggregate."""
    sqrt = math.sqrt
    one = 1.0
    two = 2.0
    total = 0.0
    for x in data:
        if x > one:
            val = sqrt(x)
            total += val * two + one / (val + one)
        elif x > 0:
            total += sqrt(x)
    return round(total, 6)
