import ast

import attrs
import pandas as pd
import numpy as np


def search_go_terms_by_embedding(
        g,
    query_embeddings: np.ndarray or list,
    n: int = .9,
    csv_path: str = "goterms/data/term_lib.csv",
) -> set[str]:
    """
    Parameters
    ----------
    query_embeddings:
        shape = (n_queries, embedding_dim)

    Returns
    -------
    set[str]
        Unique GO IDs collected from top_n hits
        across all query embeddings.
    """

    df = pd.read_csv(csv_path)

    go_ids = df["id"].tolist()

    go_embeddings = np.asarray(
        [
            ast.literal_eval(v)
            for v in df["embedding"]
        ],
        dtype=np.float32,
    )

    #
    go_embeddings /= (
        np.linalg.norm(
            go_embeddings,
            axis=1,
            keepdims=True,
        )
        + 1e-12
    )

    query_embeddings = np.asarray(
        query_embeddings,
        dtype=np.float32,
    )

    query_embeddings /= (
        np.linalg.norm(
            query_embeddings,
            axis=1,
            keepdims=True,
        )
        + 1e-12
    )

    #
    similarity = query_embeddings @ go_embeddings.T

    result = set()
    print("rows checked", len(similarity))
    for row in similarity:

        if row[1] < n:
            print("skipping", row[0], row[1], "threshold not reacheed...")
            continue
        result.add(go_ids[row[0]])

    print("similar results detected:", len(result))
    # outsrc terms
    for item in [nid for nid, attrs in g.G.nodes(data=True) if attrs.get("type") == "GO_TERM"]:
        if item not in result:
            g.delete_node(item)
    print("go terms extracted... done")
