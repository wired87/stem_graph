import ast

import numpy as np

from embedder import embed_batch


def align_function_to_term(
        g,
        n=.75,
):
    print("align processes to ")
    match_ids = set()

    functions: list[tuple[str, dict]] = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "FUNCTION_ANNOTATION"
    ]
    print("functions", [i[0] for i in functions])
    for gt_key in ["name", "text", "definition"]:
        goterms: list[tuple[str, dict]] = [
            (nid, attrs)
            for nid, attrs in g.G.nodes(data=True)
            if attrs.get("type") == "GO_TERM" and (attrs.get(gt_key))
        ]

        function_embeddings = [np.asarray(ast.literal_eval(attrs["embedding"])) for nid, attrs in functions]
        goterm_embeddings = embed_batch(
            [attrs.get(gt_key) or nid for nid, attrs in goterms]
        )

        # Convert lists to NumPy arrays for hyper-fast vectorized matrix math
        Q = np.array(function_embeddings, dtype=np.float32)
        D = np.array(goterm_embeddings, dtype=np.float32)

        # Normalize the vectors to calculate true Cosine Similarity via Dot Product
        Q_norm = Q / np.linalg.norm(Q, axis=1, keepdims=True)
        D_norm = D / np.linalg.norm(D, axis=1, keepdims=True)

        # Resulting shape: (num_fresh_queries, num_docs)
        similarity_matrix = np.dot(Q_norm, D_norm.T)

        for i, scores in enumerate(similarity_matrix):
            for j, score in enumerate(scores):
                if score > n:
                    match_ids.add(goterms[j][0])
    print("goterm fuctional alignment... done")
    return match_ids


"""


        for term_idx in matched_goterms:
            term: tuple = goterms[term_idx]

            if term[0] in terms_worked:
                continue

            terms_worked.add(term[0])

            neighbor_keywords = g.get_neighbor_list(
                node=term[0],
                target_type=outsrc_type,
                just_ids=True,
            )
            for item in neighbor_keywords:
                keep_keywords.add(item)

        if not keep_keywords:
            print("no GO-term keyword matches — keeping full keyword graph")



"""