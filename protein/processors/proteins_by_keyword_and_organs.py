import numpy as np

from embedder import embed_batch
from firegraph.graph.local_graph_utils import GUtils
from protein.processors.get_single_protein import fetch_uniprot_protein

_UNIPROT_TISSUE_MIN_SCORE = 0.75


def _edge_attr_dicts(edge_data) -> list[dict]:
    if not edge_data:
        return []
    sample = next(iter(edge_data.values()))
    if isinstance(sample, dict):
        return list(edge_data.values())
    return [edge_data]


def _query_uberon_scope(g: GUtils) -> set[str]:
    """UBERON region + anatomy children selected for this pipeline run."""
    scope: set[str] = set()
    for nid, attrs in g.G.nodes(data=True):
        if attrs.get("type") == "TISSUE" and attrs.get("sub_type") == "UBERON":
            scope.add(str(nid))
            scope.add(str(nid).replace("_", ":"))
        elif attrs.get("sub_type") == "anatomy_children":
            scope.add(str(nid))
    return scope



def _uniprot_tissues_for_query(g: GUtils) -> list[str]:
    organs: list[str] = []
    for nid, attrs in g.G.nodes(data=True):
        if attrs.get("type") != "TISSUE" or attrs.get("sub_type") != "UNIPROT":
            continue
    return organs



async def get_proteins(
    g: GUtils,
):
    """
    Receives a list of keywords and a list of target organs, runs queries concurrently,
    and returns a filtered list of matching human protein payloads.
    """
    print("get_proteins...")
    try:
        organs = [
            str(attrs.get("name") or nid)
            for nid, attrs in g.G.nodes(data=True)
            if attrs.get("type") == "TISSUE" and attrs.get("sub_type") == "UNIPROT"
        ]

        keywords = [
            nid
            for nid, attrs in g.G.nodes(data=True)
            if attrs.get("type") == "KEYWORD"
        ]

        if not keywords:
            print("no keywords in graph — skip UniProt protein fetch")
            return

        protein_rows = await fetch_uniprot_protein(
            keywords=keywords,
            organs=organs,
        )

        print("uniprot response type:", type(protein_rows))
        print("uniprot rows extracted:", len(protein_rows))

        for protein in protein_rows:
                accession = protein.get("primaryAccession")
                g.add_node(
                    attrs=dict(
                        id=accession,
                        type="PROTEIN",
                        **protein,
                        embed_key="proteinDescription__recommendedName__fullName__value",
                    )
                )

                protein_kwds = [kw["name"] for kw in protein.get("keywords", [])]


                for kwd_name in protein_kwds:
                    kwd_node = g.get_node(value=kwd_name, key="name")
                    if kwd_node is None:
                        print("add keyword node:", kwd_name)
                        kwd_node = dict(
                            id=kwd_name,
                            type="KEYWORD",
                            name=kwd_name,
                        )
                        g.add_node(kwd_node)

                    g.add_edge(
                        src=kwd_node["id"],
                        trgt=accession,
                        attrs=dict(
                            rel="describes",
                            src_layer="KEYWORD",
                            trgt_layer="PROTEIN",
                        ),
                    )

    except Exception as e:
        print("Err get proteins from organs:", e)

    count = [
        nid
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "PROTEIN"
    ]
    print("get proteins extracted:", len(count), ":\n", count, "... done")



def align_function_to_term_outsrc_ntype(
        g,
        outsrc_type="PROTEIN",
        n=.75,
):
    print("align processes to ")
    functions: list[tuple[str, dict]] = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "FUNCTION_ANNOTATION"
    ]
    print("functions", [i[0] for i in functions])

    goterms: list[tuple[str, dict]] = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "GO_TERM" and (attrs.get("text") or attrs.get("name"))
    ]

    if not functions or not goterms:
        print("align processes — missing function or GO_TERM nodes, skip keyword filter")
        return

    function_embeddings = [attrs["embedding"] for nid, attrs in functions]
    goterm_embeddings = embed_batch(
        [attrs.get("text") or attrs.get("name") or nid for nid, attrs in goterms]
    )

    # Convert lists to NumPy arrays for hyper-fast vectorized matrix math
    Q = np.array(function_embeddings, dtype=np.float32)
    D = np.array(goterm_embeddings, dtype=np.float32)

    # Normalize the vectors to calculate true Cosine Similarity via Dot Product
    Q_norm = Q / np.linalg.norm(Q, axis=1, keepdims=True)
    D_norm = D / np.linalg.norm(D, axis=1, keepdims=True)

    # Resulting shape: (num_fresh_queries, num_docs)
    similarity_matrix = np.dot(Q_norm, D_norm.T)

    matched_goterms: set[int] = set()
    for i, scores in enumerate(similarity_matrix):
        for j, score in enumerate(scores):
            if score > n:
                goterm_match = goterms[j][0]
                #print("function alignment", functions[i], " & ", goterm_match, " : ", score)
                matched_goterms.add(j)

    keep_keywords = set()
    for term_idx in matched_goterms:
        term: tuple = goterms[term_idx]
        neighbor_keywords = g.get_neighbor_list(
            node=term[0],
            target_type=outsrc_type,
            just_ids=True,
        )
        for item in neighbor_keywords:
            keep_keywords.add(item)

    if not keep_keywords:
        print("no GO-term keyword matches — keeping full keyword graph")
        return
    return keep_keywords