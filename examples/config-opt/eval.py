"""Cache simulator: score = hit rate (%) under Zipf workload.

Simulates a cache with configurable eviction policy and measures hit rate
across multiple workload patterns.
"""
import importlib, math, random, sys

sys.path.insert(0, "target")
if "config" in sys.modules:
    mod = importlib.reload(sys.modules["config"])
else:
    mod = importlib.import_module("config")

# Read config
try:
    CACHE_SIZE = int(mod.CACHE_SIZE)
    FREQ_W = float(mod.FREQUENCY_WEIGHT)
    REC_W = float(mod.RECENCY_WEIGHT)
    ADMISSION = int(mod.ADMISSION_THRESHOLD)
    PROT_RATIO = float(mod.PROTECTED_RATIO)
    PROB_RATIO = float(mod.PROBATION_RATIO)
except Exception:
    print("SCORE: 0", flush=True)
    sys.exit(0)

# Validate
if CACHE_SIZE < 1 or CACHE_SIZE > 1024:
    print("SCORE: 0", flush=True)
    sys.exit(0)
if PROT_RATIO + PROB_RATIO > 1.001 or PROT_RATIO < 0 or PROB_RATIO < 0:
    print("SCORE: 0", flush=True)
    sys.exit(0)
if ADMISSION < 1:
    print("SCORE: 0", flush=True)
    sys.exit(0)


def zipf_workload(n_items, n_requests, alpha, seed):
    """Generate Zipf-distributed access pattern."""
    rng = random.Random(seed)
    # Precompute CDF
    weights = [1.0 / (i ** alpha) for i in range(1, n_items + 1)]
    total = sum(weights)
    cdf = []
    cumsum = 0.0
    for w in weights:
        cumsum += w / total
        cdf.append(cumsum)

    requests = []
    for _ in range(n_requests):
        r = rng.random()
        # Binary search
        lo, hi = 0, len(cdf) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if cdf[mid] < r:
                lo = mid + 1
            else:
                hi = mid
        requests.append(lo)
    return requests


def simulate(workload):
    """Run cache simulation, return hit rate."""
    prot_size = max(1, int(CACHE_SIZE * PROT_RATIO))
    prob_size = max(1, int(CACHE_SIZE * PROB_RATIO))

    # Cache state: key -> {freq, last_access, segment}
    cache = {}
    access_counts = {}  # global access counts (for admission)
    hits = 0
    time_step = 0

    for key in workload:
        time_step += 1
        access_counts[key] = access_counts.get(key, 0) + 1

        if key in cache:
            hits += 1
            entry = cache[key]
            entry["freq"] += 1
            entry["last_access"] = time_step
            # Promote to protected if in probation
            if entry["segment"] == "probation":
                entry["segment"] = "protected"
        else:
            # Admission check
            if access_counts[key] < ADMISSION:
                continue

            # Need to insert — evict if full
            if len(cache) >= CACHE_SIZE:
                # Score each entry, evict lowest
                worst_key = None
                worst_score = float("inf")
                for k, e in cache.items():
                    recency = 1.0 / (1.0 + time_step - e["last_access"])
                    score = FREQ_W * e["freq"] + REC_W * recency
                    # Prefer evicting from probation
                    if e["segment"] == "probation":
                        score *= 0.5
                    if score < worst_score:
                        worst_score = score
                        worst_key = k
                if worst_key is not None:
                    del cache[worst_key]

            cache[key] = {
                "freq": 1,
                "last_access": time_step,
                "segment": "probation",
            }

    return hits / len(workload) * 100 if workload else 0


# Run multiple workload scenarios
workloads = [
    # (n_items, n_requests, alpha, seed, weight)
    (500, 10000, 1.0, 101, 1.0),    # Standard Zipf
    (200, 10000, 0.8, 102, 1.0),    # Flatter distribution
    (1000, 10000, 1.2, 103, 1.0),   # Steeper, more items
    (300, 10000, 1.0, 104, 1.0),    # Medium pool
    (500, 10000, 0.6, 105, 1.0),    # Nearly uniform (hardest)
]

total_hit_rate = 0.0
total_weight = 0.0
for n_items, n_req, alpha, seed, weight in workloads:
    wl = zipf_workload(n_items, n_req, alpha, seed)
    hr = simulate(wl)
    total_hit_rate += hr * weight
    total_weight += weight

score = total_hit_rate / total_weight
print(f"SCORE: {score:.2f}", flush=True)
