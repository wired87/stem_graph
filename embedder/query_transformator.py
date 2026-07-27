import numpy as np
from typing import List, Optional


def generate_embedding_variations(
    e: np.ndarray,
    n: int = 3,
    noise_scale: float = 0.03,
    pca_components: Optional[np.ndarray] = None,
    neighbor_embeddings: Optional[np.ndarray] = None,
    alpha_interp: float = 0.2,
    seed: Optional[int] = None,
) -> List[np.ndarray]:
    """
    Input:
        e: base embedding (d,)
    Output:
        List of n varied embeddings
    """

    if seed is not None:
        np.random.seed(seed)

    e = e / np.linalg.norm(e)  # normalize

    variations = []

    for _ in range(n):

        v = e.copy()

        # --- 1. orthogonal noise (core variation) ---
        noise = np.random.normal(size=e.shape)
        noise -= noise.dot(e) * e  # orthogonal projection
        noise /= (np.linalg.norm(noise) + 1e-8)
        v = v + noise_scale * noise

        # --- 2. PCA-based semantic shift ---
        if pca_components is not None:
            coeffs = np.random.normal(0, noise_scale, size=len(pca_components))
            delta = np.sum(coeffs[:, None] * pca_components, axis=0)
            v = v + delta

        # --- 3. interpolation with neighbors ---
        if neighbor_embeddings is not None and len(neighbor_embeddings) > 0:
            idx = np.random.randint(0, len(neighbor_embeddings))
            neighbor = neighbor_embeddings[idx]
            neighbor = neighbor / np.linalg.norm(neighbor)
            v = (1 - alpha_interp) * v + alpha_interp * neighbor

        # --- 4. renormalize ---
        v = v / (np.linalg.norm(v) + 1e-8)

        variations.append(v)

    return variations