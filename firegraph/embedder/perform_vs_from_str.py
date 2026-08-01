import numpy as np
from typing import Union, Iterable, List, Tuple
from firegraph.embedder import embed, embed_batch


def _to_matrix(data: Union[str, Iterable, np.ndarray]) -> np.ndarray:
    """Converts string, set, list, tuple, or array inputs into a 2D float32 matrix."""
    if data is None:
        return np.empty((0, 0), dtype=np.float32)

    # Convert sets or other iterables to lists
    if isinstance(data, set):
        data = list(data)

    # 1. Single string -> embed to single vector
    if isinstance(data, str):
        data = embed(data)

    # 2. Iterables (list, tuple)
    elif isinstance(data, (list, tuple)):
        if len(data) == 0:
            return np.empty((0, 0), dtype=np.float32)

        # List/Tuple of strings -> batch embed
        if isinstance(data[0], str):
            data = embed_batch(list(data))

    # 3. Convert to NumPy array
    arr = np.array(data, dtype=np.float32)

    # 4. Dimension Normalization to (N, D)
    if arr.ndim == 0 or arr.size == 0:
        return np.empty((0, 0), dtype=np.float32)
    elif arr.ndim == 1:
        arr = arr[np.newaxis, :]  # Shape (D,) -> (1, D)
    elif arr.ndim > 2:
        arr = arr.reshape(-1, arr.shape[-1])  # Collapse multi-dim tensors

    return arr


def vs(
        function_embeddings: Union[str, Iterable, np.ndarray],
        term_embeddings: Union[str, Iterable, np.ndarray],
        similarity_threshold: float = 0.8,
) -> Tuple[List[Union[int, None]], List[List[Union[int, None]]]]:
    """Performs vector similarity search across diverse input types (str, set, list, ndarray)."""
    try:
        # Standardize all inputs into 2D matrices (N, D)
        Q = _to_matrix(function_embeddings)
        D = _to_matrix(term_embeddings)

        num_functions, num_terms = Q.shape[0], D.shape[0]
        print(f"perform vs from {num_functions} to {num_terms}")

        if num_functions == 0 or num_terms == 0:
            print("Empty inputs provided; skipping vector search.")
            return [], []

        # Cosine Similarity Calculation with Zero-Division Guard
        Q_norm = Q / np.clip(np.linalg.norm(Q, axis=1, keepdims=True), 1e-8, None)
        D_norm = D / np.clip(np.linalg.norm(D, axis=1, keepdims=True), 1e-8, None)

        similarity_matrix = np.dot(Q_norm, D_norm.T)

        # Build Alignment Matrix
        alignment_matrix: List[List[Union[int, None]]] = [
            [None] * num_terms for _ in range(num_functions)
        ]

        for f_idx in range(num_functions):
            for t_idx in range(num_terms):
                if similarity_matrix[f_idx, t_idx] > similarity_threshold:
                    alignment_matrix[f_idx][t_idx] = 0

        # Collapse across functions into total alignment summary
        total_alignment: List[Union[int, None]] = [
            0 if 0 in term_alignments_across_functions else None
            for term_alignments_across_functions in zip(*alignment_matrix)
        ]

        print(f"Aligned {num_functions} active against {num_terms} passive.")
        print("vs... done")
        return total_alignment, alignment_matrix

    except Exception as e:
        print(f"Err perform vs: {e}")
        return [], []