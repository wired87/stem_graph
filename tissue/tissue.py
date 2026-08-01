from core.app_utils import _TISSLIST_URL, _UBERON_URL, CLIENT
from embedder import embed
import pandas as pd

import functools
import networkx as nx
import re


def norm(x: str) -> str:
    return re.sub(r"\s+", " ", x.lower().strip())


def link_tissue_to_sub_regions(
    g,
    paths: list[str],
):
    """
    Build graph from ASCT+B CSV files.

    Only rows containing one of the provided Uberon IDs
    are processed.

    Each non-empty cell becomes a node.

    Consecutive columns are connected:

    col1 -> col2 -> col3 -> ...
    """
    uberon_ids: list[str] = [
        key.strip().upper()
        for key, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "TISSUE"
        if attrs.get("sub_type") == "UBERON"
    ]

    for path in paths:
        print(f"Reading: {path}")

        df = pd.read_csv(path, dtype=str).fillna("")

        for row_idx, row in df.iterrows():

            values = [str(v).strip() for v in row.tolist()]

            row_uberons = [
                v for v in values
                if v.upper().startswith("UBERON:")
            ]

            if not any(u in uberon_ids for u in row_uberons):
                continue
            else:
                matched_uberon = next(
                    (
                        u
                        for u in row_uberons
                        if u in uberon_ids
                    ),
                    None,
                )

            for col_name, value in zip(df.columns, values):
                if not value:
                    continue

                if value.startswith("UBERON:"):
                    node_type = "ANATOMY"
                    rel = "partner"

                elif value.startswith("CL:"):
                    node_type = "CELL_TYPE"
                    rel = "has_cell_type"

                elif value.startswith("PCL:"):
                    node_type = "CELL_SUBTYPE"
                    rel = "has_cell"

                elif value.startswith("HGNC:"):
                    node_type = "GENE"
                    rel = "has_gene"

                elif value.startswith("ENSG"):
                    node_type = "GENE"
                    rel = "has_gene"

                elif value.startswith("UP:"):
                    node_type = "PROTEIN"
                    rel = "has"
                elif value.startswith("http"):
                    node_type = "REFERENCE"
                    rel = "to"
                else:
                    node_type = "TEXT"
                    rel = "includes"


                node_id = value

                g.add_node(
                    attrs=dict(
                        id=node_id,
                        type=node_type.upper(),
                        text=value,
                        embed_key="text",
                    )
                )

                g.add_edge(
                    matched_uberon,
                    node_id,
                    attrs=dict(
                        rel=rel,
                        src_layer="UBERON",
                        trgt_layer=node_type,
                    )
                )

        print(f"Done: {path}")




"""
Uberon
Tissue
Disease, Phenotype, Variation
Drug
Trgt (up, string)
Action/mechanism



"""


async def fetch_uniprot_tissue_vocabulary() -> list[str]:
    """
    Fetch UniProt tissue vocabulary.

    Returns:
        normalized_name -> canonical_name
    """
    resp = await CLIENT.get(_TISSLIST_URL)
    resp.raise_for_status()

    tissue_map: list = []

    for line in resp.text.splitlines():

        if line.startswith("ID   "):

            tissue: str = line[5:].rstrip(".")

            if not tissue:
                continue
            tissue_map.append(tissue)
    print("ups finished...")
    return tissue_map




@functools.lru_cache(maxsize=1)
def fetch_uberon_layer(g) -> nx.MultiGraph:
    import obonet

    obo_graph = obonet.read_obo(_UBERON_URL)

    for node_id, data in obo_graph.nodes(data=True):
        name = data.get("name")

        if not name:
            continue

        g.add_node(
            attrs=dict(
                id=node_id,
                name=name,
                type="UBERON_TERM",
                embedding=embed(name),
            )
        )

    for child_id, parent_id, edge_data in obo_graph.edges(data=True):
        child = obo_graph.nodes[child_id].get("name")
        parent = obo_graph.nodes[parent_id].get("name")

        if not child or not parent:
            continue

        rel = edge_data.get("typedef") or "is_a"

        g.add_edge(
            child,
            parent,
            attrs=dict(
                rel=rel,
                src_layer="UBERON_TERM",
                trgt_layer="UBERON_TERM",
            )
        )

    return obo_graph


def connect_uniprot_to_uberon(g) -> None:
    """Maps UniProt tissues onto Uberon ontology."""
    tissue_map = fetch_uniprot_tissue_vocabulary()
    obo_graph = fetch_uberon_layer(g)

    # 1. Build the Uberon lookup dictionary
    uberon_lookup: dict[str, tuple[str, str]] = {}

    for node_id, data in obo_graph.nodes(data=True):
        name = data.get("name")
        if not name:
            continue

        # Map the primary name
        uberon_lookup[norm(name)] = (node_id, name)

        # Map synonyms extracted via regex
        for syn in data.get("synonym", []):
            if match := re.search(r'"([^"]+)"', syn):
                uberon_lookup[norm(match.group(1))] = (node_id, name)

    # 2. Match tissues to Uberon terms
    for tissue_norm, tissue_name in tissue_map.items():
        # Exact match check (O(1) complexity)
        if tissue_norm in uberon_lookup:
            _, uberon_name = uberon_lookup[tissue_norm]
            g.add_edge(
                tissue_name,
                uberon_name,
                attrs={"rel": "ontology_match", "src_layer": "TISSUE", "trgt_layer": "UBERON_TERM"}
            )
            continue

        # Partial substring match check (Fallback)
        for uberon_norm, (_, uberon_name) in uberon_lookup.items():
            if tissue_norm in uberon_norm or uberon_norm in tissue_norm:
                g.add_edge(
                    tissue_name,
                    uberon_name,
                    attrs={"rel": "ontology_partial_match", "src_layer": "TISSUE", "trgt_layer": "UBERON_TERM"}
                )
                break




