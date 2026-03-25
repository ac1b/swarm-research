def compress(data: bytes) -> bytes:
    """Compress data. Returns compressed bytes."""
    # Naive: no compression, just return as-is with a header byte
    return b'\x00' + data


def decompress(data: bytes) -> bytes:
    """Decompress data. Must perfectly reconstruct original."""
    if not data:
        return b''
    return data[1:]
