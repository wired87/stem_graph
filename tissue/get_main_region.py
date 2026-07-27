"""
Major UBERON region lookup + cosine-similarity tissue search.

User prompt (Cursor session):
    "run and debug the query-pipe process under condition of the above
     specified coding practices"

User prompt (graph-based cache):
    "Add edges from input-node to compared (uberon, ...) nodes that include
     the identified score. Goal: graph based caching system."

The module-level ``from graph import GUtils`` previously raised
``ModuleNotFoundError`` whenever ``keyword_handler`` (and therefore
``query_pipe``) imported this file. ``GUtils`` is only referenced inside the
``if __name__ == "__main__":`` smoke block, so the correct path is imported
lazily down there and the module is now safe to import from the pipeline.
"""

import numpy as np
from embedder import embed, embed_batch
from tissue.regions import get_major_brain_uberon_regions


def search_uberon_region(
    query_tissue: str
) -> str:
    """Embeds the input query, performs a vectorized cosine similarity search

    against the hardcoded major UBERON regions (e.g. Brain), and returns the single best
    UBERON id (colon form, e.g. ``UBERON:0000955``).
    """

    regions_dict = get_major_brain_uberon_regions()
    uberon_ids = list(regions_dict.keys())
    region_names = list(regions_dict.values())

    if not region_names:
        return []

    query_embedding = embed(query_tissue)
    # Batch embeddings for the dictionary documentation strings
    doc_embeddings = embed_batch(region_names)

    # 2. Convert to NumPy arrays
    Q = np.array([query_embedding], dtype=np.float32)  # Shape: (1, dim)
    D = np.array(doc_embeddings, dtype=np.float32)  # Shape: (num_docs, dim)

    # 3. Normalize vectors for true Cosine Similarity via Dot Product
    Q_norm = Q / np.linalg.norm(Q, axis=1, keepdims=True)
    D_norm = D / np.linalg.norm(D, axis=1, keepdims=True)

    # 4. Compute similarity matrix, Shape: (1, num_docs)
    similarity_matrix = np.dot(Q_norm, D_norm.T)

    # Extract the similarity scores for our single query row
    scores = similarity_matrix[0]

    best_match_idx = int(np.argmax(scores))

    return uberon_ids[best_match_idx]

