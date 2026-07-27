"""
Vector search user queries against DISEASE embeddings already on graph nodes.

Prompt: implement point 3 — reuse disease embeddings; do not re-embed disease texts in vector_search.
"""
import numpy as np

from embedder import embed_batch

_MATCH_THRESHOLD = 0.9


async def vector_search_user_queries(
    user_queries: list[str],
    g,
) -> list[list[int]]:
    """
    Batch vector search of user queries against DISEASE node embeddings.
    Writes scored ``matches`` edges from FUNCTION_ANNOTATION_INPUT nodes.
    """
    from workflows.query_pipe import input_node_id, get_cached_matches, cache_match_edges

    disease_entries: list[tuple[str, dict]] = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "DISEASE" and attrs.get("embedding") is not None
    ]

    if not user_queries or not disease_entries:
        print("unable perform vector search: empty query or disease embeddings")
        return [[] for _ in user_queries]

    doc_embeddings = np.array(
        [attrs["embedding"] for _, attrs in disease_entries],
        dtype=np.float32,
    )
    D_norm = doc_embeddings / np.linalg.norm(doc_embeddings, axis=1, keepdims=True)

    fresh_queries: list[str] = []
    cached_by_query: dict[str, list[tuple[str, float]]] = {}
    for query in user_queries:
        cache_id = input_node_id("FUNCTION_ANNOTATION", query)
        cached = get_cached_matches(g, cache_id)
        if cached:
            cached_by_query[query] = cached
        else:
            fresh_queries.append(query)

    fresh_scores_by_query: dict[str, np.ndarray] = {}
    if fresh_queries:
        print(
            f"[*] embedding {len(fresh_queries)} fresh queries against "
            f"{len(disease_entries)} cached disease vectors..."
        )
        query_embeddings = embed_batch(fresh_queries)
        Q = np.array(query_embeddings, dtype=np.float32)
        Q_norm = Q / np.linalg.norm(Q, axis=1, keepdims=True)
        similarity_matrix = np.dot(Q_norm, D_norm.T)
        fresh_scores_by_query = {q: similarity_matrix[i] for i, q in enumerate(fresh_queries)}
    else:
        print("[*] All user queries served from graph cache; skipping query embedding.")

    results: list[list[int]] = []
    for query in user_queries:
        cache_id = input_node_id("FUNCTION_ANNOTATION", query)
        if query in fresh_scores_by_query:
            query_scores = fresh_scores_by_query[query]
            matched_indices = np.where(query_scores > _MATCH_THRESHOLD)[0].tolist()
            scored = [
                (disease_entries[i][0], float(query_scores[i])) for i in matched_indices
            ]
            n_edges = cache_match_edges(g, cache_id, scored)
            print(f"[vector_search] '{query}' -> {n_edges} cached match edges")
        else:
            cached_ids = {nid for nid, _ in cached_by_query.get(query, [])}
            matched_indices = [
                i for i, (nid, _) in enumerate(disease_entries) if nid in cached_ids
            ]
            print(f"[vector_search] '{query}' served from cache ({len(matched_indices)} matches)")

        for item in matched_indices:
            g.update_node(
                attrs=dict(
                    **disease_entries[item][1],
                    dis_match_user=True,
                    id=disease_entries[item][0],
                )
            )
        results.append(matched_indices)

    print("[+] Vector search finished.")
    return results
