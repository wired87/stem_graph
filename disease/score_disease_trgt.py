"""
Open Targets disease–target association edges for diseases already in the graph.

Prompt: implement point 2 — wire score_disease_trgt before disease embedding; protein-linked filter.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# CHAR: repo root on sys.path when this file is run as a script.
for _p in Path(__file__).resolve().parents:
    if (_p / "core").is_dir() and (_p / "embedder").is_dir():
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        break

from firegraph.file.parquet import ParquetMaster

_ASSOCIATION_URL = (
    "http://ftp.ebi.ac.uk/pub/databases/opentargets/platform/26.03/output/association_overall_direct/"
)
_ASSOCIATION_DIR = Path("disease/association")


def _norm_target_id(raw: str) -> str:
    return str(raw).strip().replace(":", "_")


def _target_ids_in_graph(g) -> set[str]:
    """OT association targetIds (Ensembl) plus UniProt accessions from PROTEIN nodes."""
    targets: set[str] = set()
    for nid, attrs in g.G.nodes(data=True):
        ntype = attrs.get("type")
        if ntype == "GENE":
            targets.add(_norm_target_id(nid))
            continue
        if ntype != "PROTEIN":
            continue
        targets.add(_norm_target_id(nid))
        for gene in attrs.get("genes") or []:
            if not isinstance(gene, dict):
                continue
            for key in ("ensemblGeneId", "geneId", "id"):
                val = gene.get(key)
                if val:
                    targets.add(_norm_target_id(str(val)))
    return targets


async def _ensure_association_parquets() -> list[Path]:
    _ASSOCIATION_DIR.mkdir(parents=True, exist_ok=True)
    valid = [p for p in sorted(_ASSOCIATION_DIR.glob("*.parquet")) if ParquetMaster.is_valid_parquet(p)]
    if not valid:
        await ParquetMaster.receive_all(
            ftp_url=_ASSOCIATION_URL,
            output_dir=str(_ASSOCIATION_DIR),
        )
        valid = [p for p in sorted(_ASSOCIATION_DIR.glob("*.parquet")) if ParquetMaster.is_valid_parquet(p)]
    if not valid:
        raise FileNotFoundError(f"no valid association parquet in {_ASSOCIATION_DIR}")
    return valid


async def score_disease_trgt(
    g,
    batch_size: int = 100_000,
) -> set[str]:
    """
    Link DISEASE nodes to in-graph targets via OT association_overall_direct.
    Returns disease ids that received at least one ``associated_with`` edge.
    """
    print("score_disease_trgt...")
    graph_targets = _target_ids_in_graph(g)
    if not graph_targets:
        print("score_disease_trgt: no GENE/PROTEIN targets in graph — skip")
        return set()

    parquet_files = await _ensure_association_parquets()
    linked_diseases: set[str] = set()

    for parquet_file in parquet_files:
        pm = ParquetMaster(str(parquet_file))
        for batch in pm.iter_batches(
            batch_size=batch_size,
            columns=[
                "diseaseId",
                "targetId",
                "aggregationType",
                "aggregationValue",
                "associationScore",
                "evidenceCount",
                "timeseries",
                "currentNovelty",
            ],
        ):
            for row in batch.to_pylist():
                disease_id = row.get("diseaseId")
                trgt_id = _norm_target_id(row.get("targetId") or "")
                if not disease_id or not trgt_id:
                    continue
                if trgt_id not in graph_targets:
                    continue
                if not g.G.has_node(disease_id):
                    continue

                g.add_edge(
                    src=disease_id,
                    trgt=trgt_id,
                    attrs=dict(
                        rel="associated_with",
                        src_layer="DISEASE",
                        trgt_layer="GENE",
                        **{k: v for k, v in row.items() if k not in ["targetId", "diseaseId"]},
                    ),
                )
                linked_diseases.add(str(disease_id))

    print(f"score_disease_trgt... done ({len(linked_diseases)} diseases linked)")
    return linked_diseases


async def collect_association_disease_ids(g) -> set[str]:
    """Disease ids in OT association parquet that hit in-graph targets (before nodes exist)."""
    graph_targets = _target_ids_in_graph(g)
    if not graph_targets:
        return set()
    parquet_files = await _ensure_association_parquets()
    disease_ids: set[str] = set()
    for parquet_file in parquet_files:
        pm = ParquetMaster(str(parquet_file))
        for batch in pm.iter_batches(batch_size=100_000, columns=["diseaseId", "targetId"]):
            for row in batch.to_pylist():
                disease_id = row.get("diseaseId")
                trgt_id = _norm_target_id(row.get("targetId") or "")
                if disease_id and trgt_id in graph_targets:
                    disease_ids.add(str(disease_id))
    return disease_ids


def protein_linked_disease_ids(g) -> set[str]:
    """Disease nodes with at least one associated_with edge to an in-graph target."""
    linked: set[str] = set()
    for nid, attrs in g.G.nodes(data=True):
        if attrs.get("type") != "DISEASE":
            continue
        for neighbor in g.G.neighbors(nid):
            edge_data = g.G.get_edge_data(nid, neighbor) or g.G.get_edge_data(neighbor, nid)
            if not edge_data:
                continue
            samples = edge_data.values() if isinstance(next(iter(edge_data.values())), dict) else [edge_data]
            for eattrs in samples:
                if isinstance(eattrs, dict) and eattrs.get("rel") == "associated_with":
                    linked.add(nid)
                    break
    return linked


if __name__ == "__main__":
    # Prompt: standalone query_pipe check — hardcoded GUtils fixture for score_disease_trgt.
    import sys
    from pathlib import Path
    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    import asyncio
    from firegraph.graph.local_graph_utils import GUtils

    async def _check_score_disease_trgt():
        # CHAR: in-graph GENE + PROTEIN xrefs for OT association parquet join.
        g = GUtils()
        g.add_node(attrs=dict(id="ENSG00000136531", type="GENE", name="SCN1A"))
        g.add_node(attrs=dict(id="P35498", type="PROTEIN", name="SCN1A", genes=["SCN1A"]))
        g.add_node(attrs=dict(id="EFO_000125", type="DISEASE", name="epilepsy", text="epilepsy"))
        g.add_edge(
            "ENSG00000136531",
            "P35498",
            attrs=dict(rel="encodes", src_layer="GENE", trgt_layer="PROTEIN"),
        )
        n0 = g.G.number_of_edges()
        linked_before = protein_linked_disease_ids(g)
        await score_disease_trgt(g, batch_size=50_000)
        assoc = [
            a for _, _, a in g.G.edges(data=True) if a.get("rel") == "associated_with"
        ]
        print(
            f"[__main__] score_disease_trgt OK  "
            f"assoc_edges={len(assoc)} linked_before={len(linked_before)} edges+={g.G.number_of_edges()-n0}"
        )

    asyncio.run(_check_score_disease_trgt())
