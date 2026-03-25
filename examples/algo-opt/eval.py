"""Bin packing eval: score = avg(lower_bound / actual_bins) * 100.

Lower bound = ceil(sum(items) / capacity). Perfect packing = 100.
Deterministic test cases with fixed seed.
"""
import importlib, math, random, sys, time

sys.path.insert(0, "target")
if "packer" in sys.modules:
    mod = importlib.reload(sys.modules["packer"])
else:
    mod = importlib.import_module("packer")

CAPACITY = 1.0

def generate_cases(seed=42):
    """Generate 8 deterministic test cases of increasing difficulty."""
    rng = random.Random(seed)
    cases = []
    # Small uniform
    cases.append([rng.uniform(0.1, 0.5) for _ in range(50)])
    # Medium uniform
    cases.append([rng.uniform(0.1, 0.7) for _ in range(100)])
    # Large items (hard to pack)
    cases.append([rng.uniform(0.3, 0.9) for _ in range(80)])
    # Many small items
    cases.append([rng.uniform(0.01, 0.2) for _ in range(300)])
    # Bimodal: mix of large and small
    cases.append([rng.choice([rng.uniform(0.6, 0.9), rng.uniform(0.05, 0.15)]) for _ in range(120)])
    # Triplet-friendly (items around 1/3)
    cases.append([rng.uniform(0.25, 0.4) for _ in range(150)])
    # Wide spread
    cases.append([rng.uniform(0.05, 0.95) for _ in range(100)])
    # Stress test
    cases.append([rng.uniform(0.1, 0.8) for _ in range(500)])
    return cases

cases = generate_cases()

# Validate correctness
total_score = 0.0
for items in cases:
    try:
        bins = mod.pack(items[:], CAPACITY)
    except Exception:
        print("SCORE: 0", flush=True)
        sys.exit(0)

    # Check: all items present
    packed = sorted(round(x, 10) for b in bins for x in b)
    expected = sorted(round(x, 10) for x in items)
    if packed != expected:
        print("SCORE: 0", flush=True)
        sys.exit(0)

    # Check: no bin exceeds capacity
    for b in bins:
        if sum(b) > CAPACITY + 1e-9:
            print("SCORE: 0", flush=True)
            sys.exit(0)

    lower_bound = math.ceil(sum(items) / CAPACITY)
    ratio = lower_bound / len(bins)
    total_score += ratio

score = (total_score / len(cases)) * 100
print(f"SCORE: {score:.2f}", flush=True)
