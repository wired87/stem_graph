import sys
from pathlib import Path
from protein.expression.hpa_cache import query_hpa_gene_ids

for _p in Path(__file__).resolve().parents:
    if (_p / "core").is_dir() and (_p / "embedder").is_dir():
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        break


def _norm(value) -> str:
    return str(value or "").strip().lower()




def include_brain_expression_hpa(
    g,
    tissue_query: str | None = None,
):
    gene_ids = list(query_hpa_gene_ids(tissue_query))
    g.add_node(
        attrs={
            "id": "GENE_IDS",
            "type": "GENE",
            "data": gene_ids,
            "tissue_query": tissue_query,
        }
    )
    print("include_brain_expression_hpa DB genes:", len(gene_ids))

