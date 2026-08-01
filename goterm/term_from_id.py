import ast
import numpy as np
from core.app_utils import DB
from firegraph.embedder.perform_vs_from_str import vs
from goterm.fetch_obo import fetch_obo


def align_term_to_fun(g) -> tuple[list[list[int | None]], list[int | None]]:
    print("load_go_term_library...")
    similarity_threshold = 0.8
    DB.create_table("GO_TERM")

    if DB.row_count("GO_TERM") == 0:
        fetch_obo(g)

    print("Loading GO cache...")

    term_node = g.get_node("GO_TERM_IDS")
    unique_term_ids: list[str] = term_node["unique"]

    functions: list[tuple[str, dict]] = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "FUNCTION_ANNOTATION"
    ]

    if not functions or not unique_term_ids:
        print("No functions or GO terms available to align.")
        return [], []

    function_embeddings = [attrs["embedding"] for nid, attrs in functions]

    # Fetch term rows from DB matching the unique IDs
    terms = DB.get_rows(
        table="GO_TERM",
        ids=unique_term_ids
    )

    term_embeddings = [
        np.asarray(ast.literal_eval(attrs["embedding"]), dtype=np.float32)
        for attrs in terms
    ]

    #
    total_alignment, alignment_matrix = vs(function_embeddings, term_embeddings)

    # 5. Update GO_TERM_IDS node
    g.update_node(
        {
            "id": "GO_TERM_IDS",
            "alignments": alignment_matrix,
            "total_alignment": total_alignment,
            "threshold": similarity_threshold,
        }
    )

    print("GO cache loaded... done")

    return total_alignment
