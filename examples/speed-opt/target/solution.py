import math

def process_data(data: list) -> float:
    """Process a list of numbers: filter, transform, aggregate."""
    result = 0.0
    sqrt = math.sqrt
    _round = round
    two = 2.0
    one = 1.0
    for x in data:
        if x > one:
            val = sqrt(x)
            result += val * two + one / (val + one)
        elif x > 0.0:
            result += sqrt(x)
    return _round(result, 6)
