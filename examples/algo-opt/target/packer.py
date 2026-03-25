def pack(items: list[float], bin_capacity: float = 1.0) -> list[list[float]]:
    """Pack items into bins using First-Fit algorithm.

    Args:
        items: list of item sizes (0 < size <= bin_capacity)
        bin_capacity: capacity of each bin

    Returns:
        list of bins, each bin is a list of item sizes
    """
    bins = []
    for item in items:
        placed = False
        for b in bins:
            if sum(b) + item <= bin_capacity:
                b.append(item)
                placed = True
                break
        if not placed:
            bins.append([item])
    return bins
