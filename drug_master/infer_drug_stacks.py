"""
Infer harmonious drug stacks from the live graph (lightweight DRUG_STACK nodes).

Prompt: infer most valuable drug stacks in harmony under DDI, tissue/BBB, phenotypes,
variants, Guide to Pharmacology validation — keep graph as light as possible.
"""
from __future__ import annotations


import itertools
from drug.drugbank_ddi import build_ddi_index, pair_ddi_severity
from drug.guidetopharmacology import GtoPdbFetcher, validate_molecule_on_targets


_CNS_UBERON_PREFIXES = ("UBERON_0000955", "UBERON_0001017", "UBERON_0002037")
_MAX_CANDIDATES = 8
_MAX_STACK_SIZE = 3
_MAX_STACKS = 5
_MAJOR_DDI_RANK = 3


def validate_ddi(g):
    """

    """
    drugs: list[tuple] = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "MOLECULE"
    ]

    #
    for nid in [[j[1] for j in i] for i in drugs]:
        neighbor_ids = g.get_neighbor_list(node=nid, target_type="PROTEIN", just_ids=True)
        








def _cns_scope(g) -> bool:
    """Query targets CNS tissue — require BBB-passing molecules."""
    for nid, attrs in g.G.nodes(data=True):
        if attrs.get("type") != "UBERON_REGION":
            continue
        uid = str(nid).replace(":", "_")
        if any(uid.startswith(p) for p in _CNS_UBERON_PREFIXES):
            return True
        name = str(attrs.get("name") or "").lower()
        if any(x in name for x in ("brain", "thalamus", "hippocampus", "cerebellum", "cortex")):
            return True
    return False


def _disease_target_proteins(g) -> set[str]:
    """PROTEIN ids linked to retained DISEASE nodes."""
    targets: set[str] = set()
    disease_ids = {
        nid for nid, a in g.G.nodes(data=True) if a.get("type") == "DISEASE"
    }
    for did in disease_ids:
        for neighbor in g.G.neighbors(did):
            nattrs = g.G.nodes.get(neighbor, {})
            if nattrs.get("type") == "PROTEIN":
                targets.add(neighbor)
            elif nattrs.get("type") == "GENE":
                targets.add(neighbor)
    return targets


def _molecule_target_set(g, nid: str) -> set[str]:
    targets: set[str] = set()
    for neighbor in g.G.neighbors(nid):
        nattrs = g.G.nodes.get(neighbor, {})
        ntype = nattrs.get("type")
        if ntype in ("PROTEIN", "GENE"):
            targets.add(neighbor)
    return targets


def _pgx_risk_count(g, molecule_nid: str) -> int:
    """Adverse pharmacogenomic hints linked to this molecule."""
    count = 0
    for neighbor in g.G.neighbors(molecule_nid):
        if g.G.nodes.get(neighbor, {}).get("type") == "PHARMACOGENOMIC_EFFECT":
            count += 1
    return count


def _candidate_molecules(g) -> list[tuple[str, dict]]:
    """MOLECULE nodes tied to disease / treatment / local targets."""
    candidates: list[tuple[str, dict]] = []
    for nid, attrs in g.G.nodes(data=True):
        if attrs.get("type") != "MOLECULE":
            continue
        if attrs.get("treatment") or attrs.get("is_drug"):
            candidates.append((nid, attrs))
            continue
        for neighbor in g.G.neighbors(nid):
            ntype = g.G.nodes.get(neighbor, {}).get("type")
            if ntype in ("DISEASE", "PROTEIN", "GENE"):
                candidates.append((nid, attrs))
                break
    return candidates


def _score_molecule(
    g,
    nid: str,
    attrs: dict,
    disease_targets: set[str],
    cns: bool,
) -> float:
    mol_targets = _molecule_target_set(g, nid)
    overlap = len(mol_targets & disease_targets)
    score = overlap * 0.35
    if attrs.get("treatment"):
        score += 0.25
    if attrs.get("is_drug"):
        score += 0.1
    if cns:
        if attrs.get("able_pass_bbb"):
            score += 0.2
        else:
            score -= 0.4
    pgx = _pgx_risk_count(g, nid)
    score -= min(pgx * 0.08, 0.24)
    return max(score, 0.0)


def _stack_harmony(
    g,
    members: list[str],
    ddi_index,
) -> tuple[float, str, list[dict]]:
    """Harmony score from DDI severity across pairs; returns max severity label."""
    if len(members) < 2:
        return 1.0, "none", []
    penalties = []
    conflicts: list[dict] = []
    max_rank = 0
    max_label = "none"
    for a, b in itertools.combinations(members, 2):
        hit = pair_ddi_severity(ddi_index, g, a, b)
        if not hit:
            continue
        rank = hit.get("rank", 0)
        max_rank = max(max_rank, rank)
        max_label = hit.get("severity", "unknown")
        penalties.append(rank * 0.25)
        if rank >= _MAJOR_DDI_RANK:
            conflicts.append({"pair": [a, b], **hit})
    harmony = max(0.0, 1.0 - sum(penalties))
    return harmony, max_label, conflicts








async def infer_drug_stacks(g) -> int:
    """
    Build top DRUG_STACK nodes (minimal attrs) + member edges only.
    Returns count of stacks added.
    """
    print("infer_drug_stacks...")






    #
    candidates = _candidate_molecules(g)
    if not candidates:
        print("infer_drug_stacks: no candidate molecules")
        return 0

    disease_targets = _disease_target_proteins(g)
    cns = _cns_scope(g)
    scored = []
    for nid, attrs in candidates:
        s = _score_molecule(g, nid, attrs, disease_targets, cns)
        if s <= 0 and cns and not attrs.get("able_pass_bbb"):
            continue
        scored.append((s, nid, attrs))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:_MAX_CANDIDATES]
    if not top:
        print("infer_drug_stacks: no scored candidates")
        return 0

    molecule_ids = [nid for _, nid, _ in top]
    ddi_index = await build_ddi_index(g, molecule_ids)
    gtop = GtoPdbFetcher()

    # CHAR: GtoP validation only for top candidates (API budget)
    gtop_flags: dict[str, bool] = {}
    for _, nid, _ in top[:5]:
        val = await validate_molecule_on_targets(g, nid, disease_targets, gtop)
        gtop_flags[nid] = val.get("validated", False)

    stacks_added = 0
    seen_members: set[frozenset[str]] = set()

    for size in range(2, _MAX_STACK_SIZE + 1):
        for combo in itertools.combinations(molecule_ids, size):
            key = frozenset(combo)
            if key in seen_members:
                continue
            harmony, ddi_label, conflicts = _stack_harmony(g, list(combo), ddi_index)
            if ddi_label == "major" or harmony < 0.4:
                continue
            stack_score = sum(s for s, nid, _ in top if nid in combo) / size
            stack_score *= harmony
            if any(gtop_flags.get(m) for m in combo):
                stack_score += 0.15
            stack_id = "STACK::" + "::".join(sorted(combo))
            g.add_node(
                attrs={
                    "id": stack_id,
                    "type": "DRUG_STACK",
                    "members": list(combo),
                    "stack_score": round(stack_score, 3),
                    "harmony_score": round(harmony, 3),
                    "bbb_required": cns,
                    "ddi_severity_max": ddi_label,
                    "gtop_validated": any(gtop_flags.get(m) for m in combo),
                    "target_coverage": len(
                        set().union(*(_molecule_target_set(g, m) for m in combo)) & disease_targets
                    ),
                    "source": "infer_drug_stacks",
                }
            )
            for member in combo:
                g.add_edge(
                    member,
                    stack_id,
                    attrs=dict(
                        rel="stack_member",
                        src_layer="MOLECULE",
                        trgt_layer="DRUG_STACK",
                    ),
                )
            for conflict in conflicts[:3]:
                pair = conflict.get("pair") or []
                if len(pair) == 2:
                    g.add_edge(
                        pair[0],
                        pair[1],
                        attrs=dict(
                            rel="ddi_conflict",
                            severity=conflict.get("severity"),
                            description=conflict.get("description"),
                            src_layer="MOLECULE",
                            trgt_layer="MOLECULE",
                            source=conflict.get("source"),
                        ),
                    )
            seen_members.add(key)
            stacks_added += 1
            if stacks_added >= _MAX_STACKS:
                break
        if stacks_added >= _MAX_STACKS:
            break

    print(f"infer_drug_stacks... done ({stacks_added} stacks, cns={cns})")
    return stacks_added
