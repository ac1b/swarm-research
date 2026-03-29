"""Compression eval: score = avg compression ratio across test inputs.

Compression ratio = original_size / compressed_size.
Ratio of 1.0 = no compression. Higher = better.
Correctness: decompress(compress(data)) must equal data exactly.
No stdlib compression modules allowed (zlib, gzip, bz2, lzma, etc).
"""
import importlib, sys, ast, random

sys.path.insert(0, "target")
try:
    if "compressor" in sys.modules:
        mod = importlib.reload(sys.modules["compressor"])
    else:
        mod = importlib.import_module("compressor")
except Exception as e:
    print(f"Import error: {e}", file=sys.stderr)
    print("SCORE: 0", flush=True)
    sys.exit(0)

# Check for banned imports
try:
    with open("target/compressor.py") as f:
        source = f.read()
    tree = ast.parse(source)
    BANNED = {"zlib", "gzip", "bz2", "lzma", "zipfile", "tarfile", "snappy", "lz4", "zstandard", "brotli"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in BANNED:
                    print("SCORE: 0", flush=True)
                    sys.exit(0)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in BANNED:
                print("SCORE: 0", flush=True)
                sys.exit(0)
except Exception:
    print("SCORE: 0", flush=True)
    sys.exit(0)


def gen_test_data():
    """Generate diverse test inputs."""
    rng = random.Random(42)
    inputs = []

    # 1. English-like text (high redundancy)
    words = ["the", "quick", "brown", "fox", "jumps", "over", "lazy", "dog",
             "and", "a", "is", "in", "it", "of", "to", "was", "for", "on",
             "are", "with", "they", "be", "at", "one", "have", "this"]
    text = " ".join(rng.choice(words) for _ in range(2000))
    inputs.append(text.encode())

    # 2. Repeated pattern
    pattern = b"ABCDEFGH" * 500
    inputs.append(pattern)

    # 3. DNA sequence (4-char alphabet)
    dna = "".join(rng.choice("ACGT") for _ in range(4000))
    inputs.append(dna.encode())

    # 4. Sparse binary (mostly zeros)
    sparse = bytearray(4000)
    for _ in range(200):
        sparse[rng.randint(0, 3999)] = rng.randint(1, 255)
    inputs.append(bytes(sparse))

    # 5. Log-like structured text
    levels = ["INFO", "WARN", "ERROR", "DEBUG"]
    modules = ["auth", "db", "api", "cache", "worker"]
    lines = []
    for i in range(200):
        lines.append(f"2024-01-{rng.randint(1,31):02d} {rng.randint(0,23):02d}:{rng.randint(0,59):02d}:{rng.randint(0,59):02d} [{rng.choice(levels)}] {rng.choice(modules)}: request processed id={rng.randint(1000,9999)}")
    inputs.append("\n".join(lines).encode())

    # 6. JSON-like data
    records = []
    for i in range(100):
        records.append(f'{{"id":{i},"name":"user_{i}","score":{rng.randint(0,100)},"active":{"true" if rng.random()>0.3 else "false"}}}')
    inputs.append(("[" + ",".join(records) + "]").encode())

    return inputs


inputs = gen_test_data()
total_ratio = 0.0

for data in inputs:
    try:
        compressed = mod.compress(data)
        decompressed = mod.decompress(compressed)
    except Exception:
        print("SCORE: 0", flush=True)
        sys.exit(0)

    # Correctness check
    if decompressed != data:
        print("SCORE: 0", flush=True)
        sys.exit(0)

    # Compression ratio
    if len(compressed) == 0:
        print("SCORE: 0", flush=True)
        sys.exit(0)

    ratio = len(data) / len(compressed)
    total_ratio += ratio

score = (total_ratio / len(inputs)) * 100
print(f"SCORE: {score:.2f}", flush=True)
