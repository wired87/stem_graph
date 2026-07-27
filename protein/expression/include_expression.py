import sys
from pathlib import Path
import numpy as np
import pandas as pd

from embedder import embed_batch
from embedder.embed_node_key import _node_embed_text

for _p in Path(__file__).resolve().parents:
    if (_p / "core").is_dir() and (_p / "embedder").is_dir():
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        break


def include_brain_expression_hpa(g):
    trgt_dir = Path(__file__).resolve().parent
    paths = sorted(trgt_dir.glob("rna*region_hpa.tsv"))

    if not paths:
        print(f"No HPA expression files found in {trgt_dir}")
        return

    for path in paths:
        if path.suffix.lower() == ".tsv":
            link_tissue_to_genes_from_tsv(
                g,
                str(path),
            )



def link_tissue_to_genes_from_tsv(
    g,
    tsv_path: str,
    similarity_threshold: float = 0.75,
):
    print("link_tissue_to_genes_from_tsv...")

    #
    tissue_list = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "TISSUE"
    ]

    print("tissues:", len(tissue_list))
    if not tissue_list:
        print("No tissue nodes available; skip HPA expression alignment")
        return

    #
    df = pd.read_csv(
        tsv_path,
        sep="\t",
        dtype=str,
    ).fillna("")

    #
    rows:list[dict] = df.to_dict("records")
    if not rows:
        print(f"No expression rows in {tsv_path}")
        return
    print("rows", len(rows))
    #
    row_texts = [
        r.get("Brain region", r.get("Subregion")) for r in rows
    ]

    #
    tissue_texts = [
        _node_embed_text(nid, attrs)
        for nid, attrs in tissue_list
    ]
    print("tissue texts:", len(tissue_texts))
    #
    tissue_vec = embed_batch(tissue_texts)
    print("tissue vecs:", len(tissue_vec))
    row_vec = embed_batch(row_texts)
    print("row vecs:", len(row_vec))

    #
    tissue_norms = np.linalg.norm(
        tissue_vec,
        axis=1,
        keepdims=True,
    )
    print("tissue norms:", len(tissue_norms))
    row_norms = np.linalg.norm(
        row_vec,
        axis=1,
        keepdims=True,
    )
    print("row norms:", len(row_norms))
    #
    similarity_matrix = (
        np.dot(tissue_vec, row_vec.T)
        / (tissue_norms @ row_norms.T)
    )
    print(" vecor search finsihed...")
    #
    match_idx_batch = []

    for tissue_idx in range(len(tissue_list)):
        print("work", tissue_idx)
        idxs = np.where(
            similarity_matrix[tissue_idx]
            >= similarity_threshold
        )[0]

        match_idx_batch.append(
            idxs.tolist()
        )

    #
    for (tissue_id, tissue_attrs), matched_idxs in zip(
        tissue_list,
        match_idx_batch,
    ):

        print(
            tissue_id,
            "matches:",
            len(matched_idxs),
        )

        for row_idx in matched_idxs:

            row = rows[row_idx]

            #
            gene_id = (
                row.get("geneId")
                or row.get("gene_id")
                or row.get("ensembl_id")
                or row.get("gene")
                or row.get("Gene")
            )

            if not gene_id:
                continue
            gene_symbol = (
                row.get("Gene")
                or row.get("gene")
                or row.get("gene_name")
                or gene_id
            )

            #
            g.add_node(
                attrs={
                    **row,
                    "id": gene_id,
                    "type": "GENE",
                    "name": gene_symbol,
                    "symbol": gene_symbol,
                    "source": "HPA",
                    "embed_key": "description",
                    "description": " ".join(
                        str(v)
                        for v in row.values()
                        if v
                    ),
                }
            )

            #
            g.add_edge(
                src=tissue_id,
                trgt=gene_id,
                attrs=dict(
                    rel="expresses",
                    src_layer="TISSUE",
                    trgt_layer="GENE",
                    score=float(
                        similarity_matrix[
                            tissue_list.index(
                                (tissue_id, tissue_attrs)
                            )
                        ][row_idx]
                    ),
                ),
            )

    print("link_tissue_to_genes_from_tsv... done")


if __name__ == "__main__":
    # Prompt: standalone query_pipe check — hardcoded GUtils + TSV for include_brain_expression_hpa.
    import sys
    from pathlib import Path
    _ROOT = Path(__file__).resolve().parents[2]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    import os
    import tempfile
    from firegraph.graph.local_graph_utils import GUtils

    # CHAR: seed Thalamus tissue node matching HPA brain-region vocabulary.
    g = GUtils()
    g.add_node(
        attrs=dict(
            id="UBERON_0001896",
            type="TISSUE",
            sub_type="UBERON",
            description="Thalamus",
            embed_key="description",
        )
    )
    # CHAR: minimal TSV row — exercises embed match + expresses edge creation.
    tsv_body = (
        "Brain region\tSubregion\tgeneId\tGene\n"
        "Thalamus\tThalamus\tENSG00000136531\tSCN1A\n"
    )
    tsv_dir = os.path.join("data", "brain_expression_hpa")
    os.makedirs(tsv_dir, exist_ok=True)
    tsv_path = os.path.join(tsv_dir, "__main_check_thalamus.tsv")
    with open(tsv_path, "w", encoding="utf-8") as fh:
        fh.write(tsv_body)
    n0, e0 = g.G.number_of_nodes(), g.G.number_of_edges()
    include_brain_expression_hpa(g)
    genes = [nid for nid, a in g.G.nodes(data=True) if a.get("type") == "GENE"]
    expresses = [
        a for _, _, a in g.G.edges(data=True) if a.get("rel") == "expresses"
    ]
    assert len(genes) >= 1 or e0 < g.G.number_of_edges(), "expected GENE or expresses edges from HPA link"
    print(f"[__main__] include_brain_expression_hpa OK  genes={len(genes)} expresses={len(expresses)}")
    g2 = GUtils()
    g2.add_node(
        attrs=dict(
            id="UBERON_0001896",
            type="TISSUE",
            description="Thalamus",
            embed_key="description",
        )
    )
    link_tissue_to_genes_from_tsv(g2, tsv_path, similarity_threshold=0.5)
    print(f"[__main__] link_tissue_to_genes_from_tsv OK  nodes={g2.G.number_of_nodes()}")
