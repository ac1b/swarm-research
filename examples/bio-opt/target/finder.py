def find_motif(sequences: list[str], k: int) -> str:
    """Find a motif of length k common to all DNA sequences.

    Args:
        sequences: list of DNA strings (alphabet: ACGT)
        k: motif length

    Returns:
        consensus motif string of length k
    """
    # Naive: return the most frequent k-mer across all sequences
    from collections import Counter
    counts = Counter()
    for seq in sequences:
        for i in range(len(seq) - k + 1):
            counts[seq[i:i + k]] += 1
    if not counts:
        return "A" * k
    return counts.most_common(1)[0][0]
