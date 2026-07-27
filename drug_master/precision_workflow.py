"""
Research-only target/pathway/drug optimisation.

This module deliberately produces dimensionless exposure factors, not patient
doses. VEP consequence predictions and ChEMBL bioactivity are evidence inputs;
they are not sufficient for prescribing or clinical decision-making.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import isfinite
from typing import Any, Iterable

from drug_master.calc_drug_trgt_score import calculate_drug_effect_score
from drug_master.influence import get_edge_multiplier


HARMFUL_CLINICAL_TERMS = {
    "pathogenic",
    "likely pathogenic",
    "drug response",
    "risk factor",
}
HARMFUL_IMPACTS = {"HIGH", "MODERATE"}


@dataclass(frozen=True)
class VariantRisk:
    variant_id: str
    protein_id: str
    harmful: bool
    direction: float
    disease_associated: bool
    evidence: dict[str, Any]


def _attrs(g, node_id: str) -> dict:
    return g.G.nodes.get(node_id, {})


def _ensure_vector(g, node_id: str, size: int) -> list[float]:
    attrs = _attrs(g, node_id)
    current = list(attrs.get("influence") or [])
    vector = [float(current[i]) if i < len(current) else 0.0 for i in range(size)]
    attrs["influence"] = vector
    return vector


def _edge_attrs(g, source: str, target: str) -> dict:
    edge = g.G.get_edge_data(source, target) or {}
    if "attrs" in edge and isinstance(edge["attrs"], dict):
        return edge["attrs"]
    return edge


def _normalise_accessions(accessions: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(
        str(item).strip().upper() for item in accessions if str(item).strip()
    ))


def add_targets(
    g,
    uniprot_accessions: Iterable[str],
    target_records: dict[str, list[dict]],
) -> list[str]:
    """Add input proteins, ChEMBL targets and dim=0 component edges."""
    accessions = _normalise_accessions(uniprot_accessions)
    target_ids = list(dict.fromkeys(
        str(row.get("target_chembl_id") or row.get("id")).strip()
        for accession in accessions
        for row in target_records.get(accession, [])
        if row.get("target_chembl_id") or row.get("id")
    ))
    target_index = {target_id: idx for idx, target_id in enumerate(target_ids)}

    for accession in accessions:
        if not g.G.has_node(accession):
            g.add_node(attrs={"id": accession, "type": "PROTEIN"})
        _ensure_vector(g, accession, len(target_ids))

        for row in target_records.get(accession, []):
            target_id = str(row.get("target_chembl_id") or row.get("id") or "").strip()
            if not target_id:
                continue
            idx = target_index[target_id]
            g.add_node(attrs={
                **row,
                "id": target_id,
                "type": "TARGET",
                "target_index": idx,
                "influence": [0.0] * len(target_ids),
            })
            g.add_edge(
                accession,
                target_id,
                attrs={
                    "rel": "target_component_of",
                    "src_layer": "PROTEIN",
                    "trgt_layer": "TARGET",
                    "dims": 0,
                    "target_index": idx,
                },
            )
    return target_ids


def add_pathways(
    g,
    pathway_rows: dict[str, list[dict]],
    vector_size: int,
    max_depth: int = 10,
) -> None:
    """Add directed pathway rows and derive minimum depth from every seed."""
    for seed, rows in pathway_rows.items():
        if not g.G.has_node(seed):
            g.add_node(attrs={"id": seed, "type": "PROTEIN"})
        _ensure_vector(g, seed, vector_size)

        for row in rows:
            source = str(row.get("source") or row.get("source_genesymbol") or seed).strip()
            target = str(row.get("target") or row.get("target_genesymbol") or "").strip()
            if not source or not target:
                continue
            for node_id in (source, target):
                if not g.G.has_node(node_id):
                    g.add_node(attrs={
                        "id": node_id,
                        "type": "PROTEIN",
                        "sub_type": "PATHWAY",
                        "influence": [0.0] * vector_size,
                    })
                else:
                    _ensure_vector(g, node_id, vector_size)
            g.add_edge(
                source,
                target,
                attrs={
                    **row,
                    "rel": "interacts_with",
                    "src_layer": "PROTEIN",
                    "trgt_layer": "PROTEIN",
                },
            )

        queue = deque([(seed, 0)])
        seen = {seed}
        while queue:
            center, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for neighbor in g.G.neighbors(center):
                if _attrs(g, neighbor).get("type") != "PROTEIN":
                    continue
                edge = _edge_attrs(g, center, neighbor)
                edge["dims"] = min(int(edge.get("dims", max_depth)), depth + 1)
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append((neighbor, depth + 1))


def classify_vep_variant(annotation: dict) -> VariantRisk:
    """Conservative VEP interpretation; disease evidence is mandatory."""
    clinical = {
        str(item).strip().lower()
        for item in annotation.get("clin_sig", annotation.get("clinical_significance", [])) or []
    }
    if isinstance(annotation.get("clin_sig"), str):
        clinical = {
            item.strip().lower()
            for item in annotation["clin_sig"].replace("&", ",").split(",")
        }
    impact = str(annotation.get("impact") or "").upper()
    phenotype = bool(
        annotation.get("phenotypes")
        or annotation.get("phenotype_or_disease")
        or annotation.get("disease")
    )
    disease_associated = phenotype and bool(
        clinical & HARMFUL_CLINICAL_TERMS or annotation.get("disease")
    )
    harmful = disease_associated and (
        impact in HARMFUL_IMPACTS or bool(clinical & HARMFUL_CLINICAL_TERMS)
    )
    effect = str(
        annotation.get("variant_effect")
        or annotation.get("effect")
        or annotation.get("consequence")
        or ""
    ).lower()
    if any(term in effect for term in ("gain_of_function", "increased")):
        direction = 1.0
    elif any(term in effect for term in (
        "loss_of_function", "decreased", "stop_gained", "frameshift"
    )):
        direction = -1.0
    else:
        direction = 0.0
    return VariantRisk(
        variant_id=str(annotation.get("id") or annotation.get("input") or "unknown"),
        protein_id=str(annotation.get("protein_id") or annotation.get("uniprot") or ""),
        harmful=harmful,
        direction=direction,
        disease_associated=disease_associated,
        evidence=dict(annotation),
    )


def _candidate_score(candidate: dict, desired_sign: float) -> float:
    try:
        score = calculate_drug_effect_score(
            float(candidate.get("activity_value")),
            str(candidate.get("activity_unit")),
            str(candidate.get("mechanism")),
            float(candidate.get("confidence", 1.0)),
        )
    except (TypeError, ValueError):
        return float("-inf")
    if desired_sign and score * desired_sign <= 0:
        return float("-inf")
    selectivity = max(0.0, min(1.0, float(candidate.get("selectivity", 1.0))))
    return abs(score) * selectivity


def select_one_drug_per_target(
    g,
    target_ids: list[str],
    candidates_by_target: dict[str, list[dict]],
    variants: list[VariantRisk],
) -> list[str]:
    """Enforce at most one MOLECULE neighbour per target."""
    harmful_by_protein = {
        risk.protein_id: risk for risk in variants if risk.harmful and risk.protein_id
    }
    selected: list[str] = []
    for target_id in target_ids:
        protein_neighbors = [
            node for node in g.G.neighbors(target_id)
            if _attrs(g, node).get("type") == "PROTEIN"
        ]
        risks = [harmful_by_protein[p] for p in protein_neighbors if p in harmful_by_protein]
        desired_sign = -risks[0].direction if risks and risks[0].direction else 0.0
        ranked = sorted(
            candidates_by_target.get(target_id, []),
            key=lambda item: _candidate_score(item, desired_sign),
            reverse=True,
        )
        ranked = [item for item in ranked if isfinite(_candidate_score(item, desired_sign))]
        if not ranked:
            continue
        candidate = ranked[0]
        drug_id = str(candidate.get("molecule_chembl_id") or candidate.get("id"))
        direct_score = calculate_drug_effect_score(
            float(candidate["activity_value"]),
            str(candidate["activity_unit"]),
            str(candidate["mechanism"]),
            float(candidate.get("confidence", 1.0)),
        )
        g.add_node(attrs={
            **candidate,
            "id": drug_id,
            "type": "MOLECULE",
            "research_only": True,
        })
        g.add_edge(
            drug_id,
            target_id,
            attrs={
                "rel": "target_of",
                "src_layer": "MOLECULE",
                "trgt_layer": "TARGET",
                "dims": 0,
                "score": direct_score,
            },
        )
        _attrs(g, target_id)["direct_drug_score"] = direct_score
        selected.append(drug_id)
    return selected


def propagate_influence(
    g,
    target_ids: list[str],
    selected_drugs: list[str],
    max_depth: int = 10,
    decay: float = 0.7,
) -> None:
    """Propagate each selected drug in its stable target-index vector slot."""
    target_index = {target_id: idx for idx, target_id in enumerate(target_ids)}
    for drug_id in selected_drugs:
        target_neighbors = [
            node for node in g.G.neighbors(drug_id)
            if _attrs(g, node).get("type") == "TARGET"
        ]
        if not target_neighbors:
            continue
        target_id = target_neighbors[0]
        idx = target_index[target_id]
        start_edge = _edge_attrs(g, drug_id, target_id)
        start_score = float(start_edge.get("score", 0.0))
        starts = [
            node for node in g.G.neighbors(target_id)
            if _attrs(g, node).get("type") == "PROTEIN"
        ]
        queue = deque((node, start_score, 0) for node in starts)
        strongest: dict[str, float] = {}
        while queue:
            center, score, depth = queue.popleft()
            if depth > max_depth or abs(strongest.get(center, 0.0)) >= abs(score):
                continue
            strongest[center] = score
            vector = _ensure_vector(g, center, len(target_ids))
            vector[idx] = score
            if depth == max_depth:
                continue
            for neighbor in g.G.neighbors(center):
                if _attrs(g, neighbor).get("type") != "PROTEIN":
                    continue
                edge = _edge_attrs(g, center, neighbor)
                multiplier = get_edge_multiplier(edge)
                if multiplier == 0.0:
                    continue
                edge["dims"] = min(int(edge.get("dims", max_depth)), depth + 1)
                queue.append((neighbor, score * multiplier * decay, depth + 1))


def add_variant_stabilisation_scores(
    g,
    variants: list[VariantRisk],
) -> None:
    """Rank target paths by depth and write normalized stabilisation weights."""
    for risk in variants:
        if not risk.harmful or not risk.protein_id or not g.G.has_node(risk.protein_id):
            continue
        reached: list[tuple[int, str, str]] = []
        queue = deque([(risk.protein_id, 0)])
        seen = {risk.protein_id}
        while queue:
            center, depth = queue.popleft()
            for neighbor in g.G.neighbors(center):
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                ntype = _attrs(g, neighbor).get("type")
                if ntype == "TARGET":
                    reached.append((depth + 1, center, neighbor))
                elif ntype == "PROTEIN" and depth < 10:
                    queue.append((neighbor, depth + 1))
        reached.sort()
        denominator = sum(range(1, len(reached) + 1)) or 1
        for rank, (depth, protein_id, target_id) in enumerate(reached, start=1):
            edge = _edge_attrs(g, protein_id, target_id)
            edge["dims"] = depth
            edge["stabilization_score"] = round(rank / denominator, 6)
            edge["variant_id"] = risk.variant_id


def optimise_safe_exposure(
    g,
    target_ids: list[str],
    selected_drugs: list[str],
    variants: list[VariantRisk],
    sex: str | None = None,
    iterations: int = 21,
) -> dict:
    """
    Grid-search each dimensionless exposure independently against all harmful
    variant residuals. This is a research ranking, never a dose calculation.
    """
    harmful = [risk for risk in variants if risk.harmful and risk.protein_id]
    factors = [0.0] * len(target_ids)
    for idx in range(len(target_ids)):
        best_factor, best_loss = 0.0, float("inf")
        for step in range(iterations):
            factor = step / max(iterations - 1, 1)
            loss = 0.0
            for risk in harmful:
                vector = _ensure_vector(g, risk.protein_id, len(target_ids))
                combined = sum(
                    vector[j] * (factor if j == idx else factors[j])
                    for j in range(len(target_ids))
                )
                desired = -risk.direction if risk.direction else 0.0
                loss += abs(desired - combined)
            if loss < best_loss:
                best_factor, best_loss = factor, loss
        factors[idx] = best_factor

    for drug_id in selected_drugs:
        drug_targets = [
            node for node in g.G.neighbors(drug_id)
            if node in target_ids
        ]
        if not drug_targets:
            continue
        target_id = drug_targets[0]
        if g.G.has_node(drug_id):
            _attrs(g, drug_id)["research_exposure_factor"] = factors[
                target_ids.index(target_id)
            ]
            _attrs(g, drug_id)["dose_unit"] = None
            _attrs(g, drug_id)["not_a_clinical_dose"] = True
    ingredient_rows = []
    for drug_id in selected_drugs:
        target_scores = {target_id: 0.0 for target_id in target_ids}
        for neighbor in g.G.neighbors(drug_id):
            if neighbor in target_scores:
                target_scores[neighbor] = float(
                    _edge_attrs(g, drug_id, neighbor).get("score", 0.0)
                )
        ingredient_rows.append({
            "drug_id": drug_id,
            "research_exposure_factor": _attrs(g, drug_id).get(
                "research_exposure_factor", 0.0
            ),
            "target_scores": target_scores,
        })

    result = {
        "target_ids": target_ids,
        "drug_ids": selected_drugs,
        "research_exposure_factors": factors,
        "ingredient_matrix": {
            "columns": target_ids,
            "rows": ingredient_rows,
        },
        "harmful_variant_count": len(harmful),
        "sex_stratum": sex,
        "sex_adjustment_applied": False,
        "clinical_use": False,
        "warning": (
            "Research prioritisation only. No dose or treatment recommendation; "
            "requires PK/PD, indication, organ function, interactions and clinician review."
        ),
    }
    g.add_node(attrs={"id": "PRECISION_DRUG_PLAN", "type": "RESEARCH_RESULT", **result})
    return result


def build_precision_drug_graph(
    g,
    uniprot_accessions: Iterable[str],
    *,
    target_records: dict[str, list[dict]],
    pathway_rows: dict[str, list[dict]],
    candidates_by_target: dict[str, list[dict]],
    vep_annotations: list[dict],
    sex: str | None = None,
) -> dict:
    """Compose the deterministic graph/scoring stages around fetched evidence."""
    variants = [classify_vep_variant(row) for row in vep_annotations]
    target_ids = add_targets(g, uniprot_accessions, target_records)
    add_pathways(g, pathway_rows, len(target_ids), max_depth=10)
    selected = select_one_drug_per_target(
        g, target_ids, candidates_by_target, variants
    )
    propagate_influence(g, target_ids, selected, max_depth=10)
    add_variant_stabilisation_scores(g, variants)
    return optimise_safe_exposure(
        g, target_ids, selected, variants, sex=sex
    )


if __name__ == "__main__":
    import json
    import os
    from pathlib import Path
    import networkx as nx
    from drug_master.live_evidence import collect_live_evidence

    class ResearchGraph:
        def __init__(self):
            self.G = nx.Graph()

        def add_node(self, attrs):
            node_id = attrs["id"]
            self.G.add_node(node_id, **{
                key: value for key, value in attrs.items() if key != "id"
            })

        def add_edge(self, source, target, attrs):
            self.G.add_edge(source, target, **attrs)

        def print_status_G(self):
            counts = {}
            for _, attrs in self.G.nodes(data=True):
                node_type = attrs.get("type", "UNKNOWN")
                counts[node_type] = counts.get(node_type, 0) + 1
            print(
                f"Graph status: {self.G.number_of_nodes()} nodes, "
                f"{self.G.number_of_edges()} edges, types={counts}"
            )

    proteins = [
        "Q15822",
        "P24046",
        "O43525",
        "Q9Y3Q4",
        "Q9P2U8",
        "Q96PR1",
        "B7Z3W4",
        "B7Z3R2",
        "B7Z3V7",
        "B2R6C6",
        "B7Z3Y0",
        "B2RCL0",
        "B4DKD3",
        "B4DKC0",
        "B4DKD1",
    ]
    offline = os.getenv("CNVMASTER_OFFLINE", "").lower() in {"1", "true", "yes"}
    evidence = (
        {
            "target_records": {protein: [] for protein in proteins},
            "pathway_rows": {protein: [] for protein in proteins},
            "candidates_by_target": {},
            "vep_annotations": [],
        }
        if offline
        else collect_live_evidence(proteins, max_depth=10)
    )
    graph = ResearchGraph()
    result = build_precision_drug_graph(
        graph,
        proteins,
        **evidence,
        sex=None,
    )
    graph_payload = {
        "result": result,
        "graph": {
            "nodes": [
                {"id": node_id, **attrs}
                for node_id, attrs in graph.G.nodes(data=True)
            ],
            "edges": [
                {"source": source, "target": target, **attrs}
                for source, target, attrs in graph.G.edges(data=True)
            ],
        },
    }
    output_path = Path("output") / "precision_drug_graph.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(graph_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(graph_payload, indent=2, sort_keys=True))
    print(f"Full graph written to: {output_path.resolve()}")
    graph.print_status_G()
