from goterm.get_terms_csv import load_go_term_library
from goterm.hierarchy import go_term_hierarchy
from keywords.go_term import GoApiFetcher


async def term_from_fun(g):
    print("term_from_fun...")
    functions: list[tuple[str, dict]] = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "FUNCTION_ANNOTATION"
    ]
    function_embeddings = [attrs["embedding"] for nid, attrs in functions]

    # include goterms
    gids = load_go_term_library(g, function_embeddings)

    # todo get hierarchy
    fetcher = GoApiFetcher()
    await go_term_hierarchy(fetcher, g, gids)
    print("term_from_fun... done")

