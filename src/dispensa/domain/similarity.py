from collections.abc import Sequence
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray


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


def unit_rows(vectors: Sequence[Sequence[float]]) -> NDArray[np.float64]:
    """Stack vectors into a matrix whose rows are scaled to unit length.

    A zero vector stays zero, so it scores 0.0 against anything, as
    cosine_similarity does. Every vector must have the same length.
    """
    lengths = {len(vector) for vector in vectors}
    if len(lengths) > 1:
        msg = f"Vector lengths must match, got {sorted(lengths)}"
        raise ValueError(msg)
    matrix = np.asarray(vectors, dtype=np.float64)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.where(norms == 0.0, 1.0, norms)


def cosine_scores(
    unit_matrix: NDArray[np.float64],
    query: Sequence[float],
) -> NDArray[np.float64]:
    """Return the cosine similarity of query against every row of unit_matrix."""
    vector = np.asarray(query, dtype=np.float64)
    if unit_matrix.shape[1] != vector.shape[0]:
        msg = (
            f"Vector lengths must match, got {unit_matrix.shape[1]} "
            f"and {vector.shape[0]}"
        )
        raise ValueError(msg)
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        return np.zeros(unit_matrix.shape[0])
    return unit_matrix @ (vector / norm)
