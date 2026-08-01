from __future__ import annotations

from typing import BinaryIO


def build_config(functional_annotation: str, threshold: float) -> dict:
    functions = [value.strip() for value in functional_annotation.replace("\n", ",").split(",") if value.strip()]
    return {"protein": {"functional_annotation": functions,
                        "function_similarity_threshold": float(threshold)}}


def run_stem_graph(*, files: list[BinaryIO], annotate_variants: bool = False,
                   functional_annotation: str = "", function_similarity_threshold: float = 0.75):
    """Execute StemCNV using byte-stream inputs and return plain response data."""
    import networkx as nx
    from product.run_local import run_local
    from product.stem_graph_table import build_stem_graph_table

    graph = run_local(files, annotate_variants=annotate_variants,
                      cfg=build_config(functional_annotation, function_similarity_threshold))
    serializable = graph.check_serilize(graph.G)
    payload = {
        "status": "complete",
        "summary": {"nodes": serializable.number_of_nodes(), "edges": serializable.number_of_edges(),
                    "samples": len(graph.workflow_result.get("result_ids", []))},
        "workflow_result": graph.workflow_result,
        "graph": nx.node_link_data(serializable),
        "stem_graph_table": build_stem_graph_table(serializable),
    }
    return graph, payload


if __name__ == "__main__":
    print(build_config("DNA repair, chromosome segregation", 0.75))
