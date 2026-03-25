"""Cache configuration parameters to optimize."""

# Cache size (number of slots)
CACHE_SIZE = 64

# Eviction: when cache is full, evict the entry with lowest priority.
# priority = frequency_weight * freq + recency_weight * recency_score
FREQUENCY_WEIGHT = 1.0
RECENCY_WEIGHT = 0.0

# Admission: only cache items accessed at least this many times
ADMISSION_THRESHOLD = 1

# Segment sizes for segmented LRU (fraction of CACHE_SIZE)
# protected_ratio + probation_ratio must be <= 1.0
PROTECTED_RATIO = 0.5
PROBATION_RATIO = 0.5
