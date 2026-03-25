---
target: target/config.py
eval: python3 eval.py
direction: maximize
rounds: 10
backtrack: 3
max_backtracks: 3
timeout: 30
---
Optimize cache configuration parameters for maximum hit rate.

**Goal:** Tune the parameters in `config.py` to maximize cache hit rate across 5 diverse Zipf workloads.

**Parameters you can tune:**
- `CACHE_SIZE` — number of cache slots (1-1024)
- `FREQUENCY_WEIGHT` — weight of access frequency in eviction scoring
- `RECENCY_WEIGHT` — weight of recency in eviction scoring
- `ADMISSION_THRESHOLD` — minimum access count before caching an item
- `PROTECTED_RATIO` — fraction of cache for protected segment
- `PROBATION_RATIO` — fraction of cache for probation segment

**Constraints:**
- CACHE_SIZE must be between 1 and 1024
- PROTECTED_RATIO + PROBATION_RATIO <= 1.0
- ADMISSION_THRESHOLD >= 1
- All values must be valid Python literals

**Scoring:** Average hit rate (%) across 5 workloads with varying Zipf parameters and item pool sizes.
