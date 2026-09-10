from collections.abc import Sequence


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Return the cosine similarity between two vectors."""
    if len(a) != len(b):
        msg = f"Vector lengths must match, got {len(a)} and {len(b)}"
        raise ValueError(msg)

    dot = sum(left * right for left, right in zip(a, b, strict=True))
    norm_a = float(sum(value * value for value in a) ** 0.5)
    norm_b = float(sum(value * value for value in b) ** 0.5)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(dot / (norm_a * norm_b))
