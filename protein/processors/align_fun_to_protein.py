import numpy as np

from embedder import embed_batch


def align_fun_to_protein(
        g,
        n=.75,
):
    print("align processes to ")
    functions: list[tuple[str, dict]] = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "FUNCTION_ANNOTATION"
    ]
    print("functions:", [i[0] for i in functions])

    proteins: list[tuple[str, dict]] = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "PROTEIN"
    ]

    function_embeddings = [attrs["embedding"] for nid, attrs in functions]
    protein_embeddings = embed_batch(
        [attrs['comments'][0]['texts'][0]['value'] or nid for nid, attrs in proteins]
    )

    # Convert lists to NumPy arrays for hyper-fast vectorized matrix math
    Q = np.array(function_embeddings, dtype=np.float32)
    D = np.array(protein_embeddings, dtype=np.float32)

    # Normalize the vectors to calculate true Cosine Similarity via Dot Product
    Q_norm = Q / np.linalg.norm(Q, axis=1, keepdims=True)
    D_norm = D / np.linalg.norm(D, axis=1, keepdims=True)

    # Resulting shape: (num_fresh_queries, num_docs)
    similarity_matrix = np.dot(Q_norm, D_norm.T)

    matched_goterms: set[str] = set()
    for i, scores in enumerate(similarity_matrix):
        for j, score in enumerate(scores):
            if score > n:
                goterm_match = proteins[j][0]
                #print("function alignment", functions[i], " & ", goterm_match, " : ", score)
                matched_goterms.add(goterm_match)
    return matched_goterms



