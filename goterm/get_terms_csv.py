from pathlib import Path

from core.app_utils import DB
from goterm.fetch_obo import fetch_obo

GO_TERM_CACHE = Path("goterms/data/term_lib.csv")


def load_go_term_library(g, function_embeddings) -> list[str]:
    print("load_go_term_library...")
    DB.create_table("GO_TERM")

    if DB.row_count("GO_TERM") == 0:
        fetch_obo(g)

    print("Loading GO cache...")

    # GET ROWS
    ids = DB.perform_vs(
        table="GO_TERM",
        embedding_comparishon=function_embeddings
    )

    for item in ids:
        """
        dict(
            id=row["id"],
            name=row["name"],
            namespace=row["namespace"],
            embedding=embedding,
            type="GO_TERM",
            sub_type="GO",
            embed_key="name", 
        )
        """
        g.add_node(
            attrs={"id":item, "type": "GO_TERM"}
        )

    #
    goterms = [
        nid for nid, attrs in g.G.nodes(data=True) if attrs.get("type") == "GO_TERM"
    ]

    for nid in goterms:
        if nid not in ids:
            g.delete_node(nid)

    goterms = [
        nid for nid, attrs in g.G.nodes(data=True) if attrs.get("type") == "GO_TERM"
    ]

    print("goterms left", len(goterms))
    print("GO cache loaded... done")
    return ids


