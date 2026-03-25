"""Sorting module. Optimize for speed while maintaining correctness."""
from config import THRESHOLD, CHUNK_SIZE


def sort(data):
    """Sort a list of numbers. Must return a correctly sorted list."""
    # Naive bubble sort — slow but correct
    arr = list(data)
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr
