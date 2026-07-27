"""
Extract ChEMBL IC50/Ki potency from MOLECULE→PROTEIN activity edges.

Prompt: industrial drug stack ranking — potency from available bioactivity parameters.
"""
from __future__ import annotations

import math


def _nm_to_potency_score(value_nm: float) -> float:
    """Higher score = stronger binding (lower nM). Log-scaled 0..1."""
    if value_nm <= 0:
        return 0.0
    # CHAR: 1 nM -> ~1.0, 10 µM -> ~0.0
    return max(0.0, min(1.0, 1.0 - math.log10(value_nm) / 5.0))


def molecule_potency_score(g, molecule_nid: str) -> float:
    """Best (lowest) IC50/Ki among activity edges for this molecule."""
    best_nm: float | None = None
    for neighbor in g.G.neighbors(molecule_nid):
        edge_bundle = g.G.get_edge_data(molecule_nid, neighbor)
        if not edge_bundle:
            continue
        for eattrs in edge_bundle.values():
            if not isinstance(eattrs, dict):
                continue
            if eattrs.get("rel") not in ("drug_combination_trgt", "activity_on_target"):
                continue
            val = eattrs.get("standard_value")
            units = str(eattrs.get("standard_units") or "nM").lower()
            stype = str(eattrs.get("standard_type") or "").upper()
            if val is None or stype not in ("IC50", "KI", "KD", "EC50"):
                continue
            try:
                v = float(val)
            except (TypeError, ValueError):
                continue
            if units == "um" or units == "µm":
                v *= 1000.0
            if best_nm is None or v < best_nm:
                best_nm = v
    if best_nm is None:
        return 0.0
    return _nm_to_potency_score(best_nm)


def stack_potency_score(g, members: list[str]) -> float:
    if not members:
        return 0.0
    scores = [molecule_potency_score(g, m) for m in members]
    return sum(scores) / len(scores)
