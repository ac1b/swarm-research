import math

def process_data(data: list) -> float:
    """Process a list of numbers: filter, transform, aggregate."""
    result = 0.0
    sqrt = math.sqrt
    for x in data:
        if x > 1.0:
            val = sqrt(x)
            result += val * 2.0 + 1.0 / (val + 1.0)
        elif x > 0.0:
            result += sqrt(x)
    return round(result, 6)
