---
target: target/compressor.py
eval: python3 eval.py
direction: maximize
rounds: 10
backtrack: 3
max_backtracks: 3
timeout: 60
---
Implement a compression algorithm that maximizes compression ratio.

**Goal:** Write `compress(data)` and `decompress(data)` functions that achieve the highest compression ratio across 6 diverse data types.

**Rules:**
- `decompress(compress(data))` must return the original data exactly
- No stdlib compression modules: zlib, gzip, bz2, lzma, zipfile, tarfile
- No external packages — pure Python stdlib only
- Both functions take and return `bytes`

**Scoring:** avg(original_size / compressed_size) * 100 across 6 test inputs. Baseline (no compression) = ~100. Higher = better.

**Test data types:** English text, repeated patterns, DNA sequences, sparse binary, server logs, JSON records.

**Approaches to explore:** Run-length encoding, Huffman coding, LZ77/LZ78, dictionary compression, hybrid schemes.
