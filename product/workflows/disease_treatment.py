"""Evidence-preserving disease/variant/drug nodes for ``StemGraph``.

The module intentionally separates predicted consequence, disease association,
target-activity direction, and pharmacogenomic response.  Those concepts are
not interchangeable and an unknown value is never coerced to a binary class.
"""
from __future__ import annotations

from collections.abc import Mapping


INCREASE_ACTIONS = {"ACTIVATOR", "AGONIST", "INDUCER", "POSITIVE MODULATOR"}
DECREASE_ACTIONS = {
    "INHIBITOR", "ANTAGONIST", "BLOCKER", "NEGATIVE MODULATOR", "DEGRADER"
}
PATHOGENIC_TERMS = {"pathogenic", "likely pathogenic"}


def treatment_config(cfg):
    if not isinstance(cfg, Mapping):
        return {}
    value = cfg.get("treatment", cfg.get("disease_treatment", {}))
    return value if isinstance(value, Mapping) else {}


def disease_treatment_enabled(cfg):
    params = treatment_config(cfg)
    return bool(params.get("enabled") or params.get("pharmacogenetic_entries"))


def _add_data_node(graph, node_id, node_type, data, **attrs):
    graph.add_node(
        {"id": node_id, "type": node_type, "data": data, **attrs}
    )


def _variants(graph):
    return [
        (node_id, attrs)
        for node_id, attrs in graph.G.nodes(data=True)
        if attrs.get("type") == "VARIANT"
    ]


def _clinical_terms(payload):
    value = payload.get("clin_sig", payload.get("clinical_significance", []))
    if isinstance(value, str):
        value = value.replace("&", ",").split(",")
    return {str(item).strip().lower() for item in value or []}


def _clinical_assertions(attrs):
    """Yield VEP root/colocated records that can carry ClinVar assertions."""
    payload = (
        attrs.get("annotation")
        if isinstance(attrs.get("annotation"), Mapping)
        else attrs
    )
    yield payload
    for row in payload.get("colocated_variants", []) or []:
        if isinstance(row, Mapping):
            yield row


def _is_harmful(attrs):
    """Return True only for a disease-linked pathogenic clinical assertion.

    VEP consequence severity predicts molecular impact, not pathogenicity.
    ClinVar annotations returned in ``colocated_variants`` are therefore used
    when available; ``HIGH`` impact alone is deliberately insufficient.
    """
    for payload in _clinical_assertions(attrs):
        has_disease = bool(
            payload.get("disease")
            or payload.get("phenotype_or_disease")
            or payload.get("phenotypes")
            or payload.get("phenotype")
        )
        if has_disease and (_clinical_terms(payload) & PATHOGENIC_TERMS):
            return True
    return False


def _normalise_direction(value):
    value = str(value or "").strip().upper()
    if value == "INCREASE":
        return 0
    if value == "DECREASE":
        return 1
    return None


def _row_drug_ids(row):
    values = row.get("drugs", row.get("drugIds", [])) or []
    if isinstance(values, (str, Mapping)):
        values = [values]
    result = []
    for item in values:
        value = item.get("drugId") if isinstance(item, Mapping) else item
        if value:
            result.append(str(value))
    return result


def _row_targets(row):
    values = (
        row.get("targets")
        or row.get("targetIds")
        or row.get("targetId")
        or row.get("targetFromSourceId")
        or row.get("target_chembl_id")
        or []
    )
    if isinstance(values, (str, Mapping)):
        values = [values]
    result = set()
    for item in values:
        value = (
            item.get("id")
            or item.get("targetId")
            or item.get("target_chembl_id")
            if isinstance(item, Mapping)
            else item
        )
        if value:
            result.add(str(value))
    return result


def _variant_targets(graph, variant_id, attrs):
    payload = attrs.get("annotation") if isinstance(attrs.get("annotation"), Mapping) else attrs
    targets = {
        str(value)
        for key in ("gene_id", "protein_id", "uniprot")
        for value in ([payload.get(key)] if payload.get(key) else [])
    }
    if graph.G.has_node(variant_id):
        for effect_id in graph.G.neighbors(variant_id):
            effect = graph.G.nodes.get(effect_id, {})
            if effect.get("type") != "VARIANT_EFFECT":
                continue
            effect_payload = effect.get("data", {})
            for key in ("gene_id", "protein_id"):
                if effect_payload.get(key):
                    targets.add(str(effect_payload[key]))
            for neighbor in graph.G.neighbors(effect_id):
                if graph.G.nodes.get(neighbor, {}).get("type") in {"GENE", "PROTEIN"}:
                    targets.add(str(neighbor))
    return targets


def _mechanism_action(row):
    action = str(
        row.get("actionType")
        or row.get("action_type")
        or row.get("action")
        or ""
    ).upper()
    if action in INCREASE_ACTIONS:
        return 0
    if action in DECREASE_ACTIONS:
        return 1
    return None


def build_disease_treatment_nodes(graph, cfg):
    """Build index-stable evidence nodes and conservative treatment candidates."""
    params = treatment_config(cfg)
    variants = _variants(graph)
    variant_ids = [variant_id for variant_id, _ in variants]
    variant_index = {variant_id: idx for idx, variant_id in enumerate(variant_ids)}
    harmful = [0 if _is_harmful(attrs) else None for _, attrs in variants]
    _add_data_node(
        graph, "harmful_variation", "HARMFUL_VARIATION", harmful,
        variants=variant_ids,
        semantics="0=explicit disease-associated pathogenic evidence; None=not established",
    )

    entries = [
        row for row in params.get("pharmacogenetic_entries", [])
        if isinstance(row, Mapping) and str(row.get("variantId") or "") in variant_index
    ]
    rows_by_variant = {variant_id: [] for variant_id in variant_ids}
    for row in entries:
        rows_by_variant[str(row["variantId"])].append(row)

    directions = []
    raw_directions = []
    drug_ids_by_variant = []
    for variant_id in variant_ids:
        rows = rows_by_variant[variant_id]
        observed = {_normalise_direction(row.get("directionality")) for row in rows}
        observed.discard(None)
        directions.append(next(iter(observed)) if len(observed) == 1 else None)
        raw_directions.append([row.get("directionality") for row in rows])
        drug_ids_by_variant.append(sorted({
            drug_id for row in rows for drug_id in _row_drug_ids(row)
        }))

    all_drug_ids = sorted({item for row in drug_ids_by_variant for item in row})
    drug_index = {drug_id: idx for idx, drug_id in enumerate(all_drug_ids)}
    indexed_drugs = [
        [drug_index[drug_id] for drug_id in row] for row in drug_ids_by_variant
    ]
    direction_semantics = params.get(
        "direction_semantics", "pharmacogenomic_response"
    )
    _add_data_node(
        graph, "variant_dir", "VARIANT_DIRECTION", directions,
        variants=variant_ids,
        raw_directionality=raw_directions,
        coding={"INCREASE": 0, "DECREASE": 1, "unknown_or_conflicting": None},
        semantics=direction_semantics,
    )
    _add_data_node(
        graph, "DRUGIDS", "DRUG_IDS", all_drug_ids, index_by_id=drug_index
    )
    _add_data_node(
        graph, "VAR_DRUG_IDS", "VARIANT_DRUG_IDS", indexed_drugs,
        variants=variant_ids,
    )

    mechanisms = [
        row for row in params.get("mechanism_entries", [])
        if isinstance(row, Mapping)
    ]
    accepted = [[] for _ in variant_ids]
    evidence = [[] for _ in variant_ids]
    inference_allowed = direction_semantics == "target_activity"
    if inference_allowed:
        for variant_idx, (variant_id, attrs) in enumerate(variants):
            direction = directions[variant_idx]
            if harmful[variant_idx] is None or direction is None:
                continue
            variant_targets = _variant_targets(graph, variant_id, attrs)
            for drug_idx in indexed_drugs[variant_idx]:
                drug_id = all_drug_ids[drug_idx]
                for mechanism in mechanisms:
                    mechanism_drugs = (
                        mechanism.get("chemblIds")
                        or mechanism.get("drugIds")
                        or mechanism.get("drugId")
                        or mechanism.get("molecule_chembl_id")
                        or mechanism.get("parent_molecule_chembl_id")
                        or []
                    )
                    if isinstance(mechanism_drugs, str):
                        mechanism_drugs = [mechanism_drugs]
                    if drug_id not in mechanism_drugs:
                        continue
                    mechanism_targets = _row_targets(mechanism)
                    if not variant_targets.intersection(mechanism_targets):
                        continue
                    action = _mechanism_action(mechanism)
                    if action is not None and action != direction:
                        accepted[variant_idx].append(drug_idx)
                        evidence[variant_idx].append(dict(mechanism))
                        break
            accepted[variant_idx] = sorted(set(accepted[variant_idx]))

    _add_data_node(
        graph, "VAR_TREATMENT_DRUG_IDS", "VARIANT_TREATMENT_DRUG_IDS", accepted,
        variants=variant_ids,
        evidence=evidence,
        inference_allowed=inference_allowed,
        warning=(
            None if inference_allowed else
            "No opposite-mechanism inference: pharmacogenomic response "
            "direction is not target-activity direction."
        ),
    )
    return accepted
