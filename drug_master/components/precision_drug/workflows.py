from __future__ import annotations

from pathlib import Path
from typing import Callable


def run_precision_drug_workflow(*, graph, accessions: list[str], vep_annotations: list[dict],
                                sex: str | None, directory: Path,
                                download_url: Callable[[str], str]):
    """Run the research pipeline using only primitive values and a graph service."""
    from drug_master.artifacts import build_artifacts
    from drug_master.live_evidence import collect_live_evidence
    from drug_master.precision_workflow import build_precision_drug_graph

    evidence = collect_live_evidence(accessions, max_depth=10)
    evidence["vep_annotations"] = vep_annotations
    result = build_precision_drug_graph(graph, accessions, **evidence, sex=sex or None)
    payload = graph.payload()
    artifacts = build_artifacts(graph, result, directory=directory, download_url=download_url)
    result.update({
        "nx_graph_file_path": artifacts["nx_graph"]["url"],
        "order_pdf_path": artifacts["order_pdf"]["url"],
        "process_sum_pdf_path": artifacts["process_pdf"]["url"],
    })
    return result, payload, artifacts


if __name__ == "__main__":
    print({"accessions": ["Q15822"], "vep_annotations": [], "sex": None,
           "note": "Validated CLI mock; real execution is exposed through run_precision_drug_workflow()."})
