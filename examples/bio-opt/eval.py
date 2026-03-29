"""Planted motif search eval.

Each test case plants a known motif (with mutations) into random DNA sequences.
The finder must recover the original motif.
Score = avg(hamming_similarity to true motif) * 100.
"""
import importlib, random, sys

sys.path.insert(0, "target")
try:
    if "finder" in sys.modules:
        mod = importlib.reload(sys.modules["finder"])
    else:
        mod = importlib.import_module("finder")
except Exception as e:
    print(f"Import error: {e}", file=sys.stderr)
    print("SCORE: 0", flush=True)
    sys.exit(0)

ALPHABET = "ACGT"


def plant_motif(motif, seq_length, n_seqs, n_mutations, rng):
    """Generate sequences with a planted motif (possibly mutated)."""
    k = len(motif)
    sequences = []
    for _ in range(n_seqs):
        seq = [rng.choice(ALPHABET) for _ in range(seq_length)]
        # Plant motif with random mutations
        pos = rng.randint(0, seq_length - k)
        planted = list(motif)
        if n_mutations > 0:
            mut_positions = rng.sample(range(k), min(n_mutations, k))
            for p in mut_positions:
                planted[p] = rng.choice([c for c in ALPHABET if c != motif[p]])
        seq[pos:pos + k] = planted
        sequences.append("".join(seq))
    return sequences


def hamming_similarity(a, b):
    """Fraction of matching characters."""
    if len(a) != len(b):
        return 0.0
    return sum(c1 == c2 for c1, c2 in zip(a, b)) / len(a)


rng = random.Random(42)

# Generate true motifs (fixed seed for reproducibility)
true_motifs = [
    "".join(rng.choice(ALPHABET) for _ in range(k))
    for k in [6, 8, 8, 10, 10, 12]
]

# Test cases: (motif, seq_length, n_seqs, n_mutations)
test_cases = [
    (true_motifs[0], 100, 20, 1),    # Easy: 6-mer, 1 mutation, short seqs
    (true_motifs[1], 150, 20, 1),    # Easy: 8-mer, 1 mutation
    (true_motifs[2], 200, 15, 2),    # Medium: 8-mer, 2 mutations
    (true_motifs[3], 250, 20, 2),    # Medium: 10-mer, 2 mutations
    (true_motifs[4], 300, 15, 3),    # Hard: 10-mer, 3 mutations
    (true_motifs[5], 400, 15, 3),    # Hard: 12-mer, 3 mutations, long seqs
]

total_sim = 0.0
for motif, seq_len, n_seqs, n_mut in test_cases:
    k = len(motif)
    sequences = plant_motif(motif, seq_len, n_seqs, n_mut, rng)

    try:
        found = mod.find_motif(sequences, k)
    except Exception:
        print("SCORE: 0", flush=True)
        sys.exit(0)

    if not isinstance(found, str) or len(found) != k:
        print("SCORE: 0", flush=True)
        sys.exit(0)

    if not all(c in ALPHABET for c in found):
        print("SCORE: 0", flush=True)
        sys.exit(0)

    total_sim += hamming_similarity(found, motif)

score = (total_sim / len(test_cases)) * 100
print(f"SCORE: {score:.2f}", flush=True)
