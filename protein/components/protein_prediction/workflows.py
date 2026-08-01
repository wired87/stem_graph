from __future__ import annotations

import asyncio
from typing import Any


def filter_protein_entries(graph: Any) -> list[dict]:
    filtered = []
    for node_id, attrs in graph.nodes_by_type("PROTEIN"):
        description = attrs.get("proteinDescription") or {}
        recommended = description.get("recommendedName") or {}
        full_name = recommended.get("fullName") or {}
        genes = attrs.get("genes") or []
        first_gene = genes[0] if genes and isinstance(genes[0], dict) else {}
        comments = attrs.get("comments") or []
        first_comment = comments[0] if comments and isinstance(comments[0], dict) else {}
        texts = first_comment.get("texts") or []
        first_text = texts[0] if texts and isinstance(texts[0], dict) else {}
        filtered.append({
            "id": node_id,
            "description": full_name.get("value", "unknown"),
            "gene": (first_gene.get("geneName") or {}).get("value", "unknown"),
            "text": first_text.get("value", "unknown"),
            "score": attrs.get("protein_score", 0),
            "evidence": attrs.get("evidence", {}),
        })
    return sorted(filtered, key=lambda item: item["score"], reverse=True)


def run_protein_prediction(
    *, tissue: str, functional_annotation: str, protein_type: str = ""
) -> tuple[Any, dict]:
    """Run the protein service with primitive, framework-independent values."""
    from protein.workflow import predict_proteins

    graph = asyncio.run(predict_proteins(
        tissue=tissue,
        functional_annotation=functional_annotation,
        protein_type=protein_type or None,
    ))
    return graph, {"proteins": filter_protein_entries(graph)}


if __name__ == "__main__":
    # Offline CLI smoke data exercises the output contract without web calls.
    class MockGraph:
        def nodes_by_type(self, _node_type):
            return [("PTEST", {"protein_score": 0.91})]

    print({"proteins": filter_protein_entries(MockGraph())})
