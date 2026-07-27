"""
Industrial composite ranking for DRUG_STACK nodes (minimal graph updates).

Prompt: predict best working drug stack under all available parameters — production ranking.
"""
from __future__ import annotations

from drug.ic50_potency import molecule_potency_score, stack_potency_score


def _stack_members(attrs: dict) -> list[str]:
    raw = attrs.get("members") or []
    return [str(x) for x in raw if x]


async def rank_drug_stacks(g) -> int:
    """
    Re-score DRUG_STACK nodes → ``industrial_score`` + ``rank_index``.
    Uses existing stack_score, harmony, potency, GtoP flag, target coverage.
    """
    print("rank_drug_stacks...")
    stacks: list[tuple[str, dict]] = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "DRUG_STACK"
    ]
    if not stacks:
        print("rank_drug_stacks: no DRUG_STACK nodes")
        return 0

    ranked: list[tuple[float, str, dict]] = []
    max_coverage = 1
    for nid, attrs in stacks:
        members = _stack_members(attrs)
        coverage = int(attrs.get("target_coverage") or 0)
        max_coverage = max(max_coverage, coverage)

    for nid, attrs in stacks:
        members = _stack_members(attrs)
        stack_score = float(attrs.get("stack_score") or 0.0)
        harmony = float(attrs.get("harmony_score") or 0.0)
        potency = stack_potency_score(g, members)
        gtop = 1.0 if attrs.get("gtop_validated") else 0.0
        coverage = int(attrs.get("target_coverage") or 0)
        coverage_norm = coverage / max_coverage if max_coverage else 0.0
        ddi_penalty = 0.15 if attrs.get("ddi_severity_max") == "moderate" else 0.0

        industrial = (
            0.30 * min(stack_score, 1.5)
            + 0.25 * harmony
            + 0.25 * potency
            + 0.10 * gtop
            + 0.10 * coverage_norm
            - ddi_penalty
        )
        industrial = max(0.0, round(industrial, 4))
        ranked.append((industrial, nid, attrs))

    ranked.sort(key=lambda x: x[0], reverse=True)
    for idx, (score, nid, attrs) in enumerate(ranked, start=1):
        members = _stack_members(attrs)
        for mid in members:
            mol_attrs = g.G.nodes.get(mid, {})
            g.update_node(
                attrs=dict(
                    **mol_attrs,
                    id=mid,
                    potency_score=round(molecule_potency_score(g, mid), 4),
                )
            )
        g.update_node(
            attrs=dict(
                **attrs,
                id=nid,
                industrial_score=score,
                rank_index=idx,
                potency_score=round(stack_potency_score(g, members), 4),
            )
        )

    print(f"rank_drug_stacks... done (top={ranked[0][0]:.3f}, n={len(ranked)})")
    return len(ranked)
