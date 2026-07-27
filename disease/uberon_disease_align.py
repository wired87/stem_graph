"""
UBERON alignment for Open Targets diseases via HPO phenotypes + biosample tree.

Prompt: does open targets disease phenotype include a uberon id? implement lookup alignment.
Note: disease_phenotype.parquet uses HPO (HP_*) — UBERON via HPO xrefs + OT biosample hierarchy.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import httpx
import pyarrow.parquet as pq

from firegraph.file.parquet import ParquetMaster

# CHAR: OT exports used for anatomy-aware disease filtering
_DISEASE_PHENOTYPE_URL = (
    "http://ftp.ebi.ac.uk/pub/databases/opentargets/platform/26.03/output/disease_phenotype/"
)
_BIOSAMPLE_URL = (
    "http://ftp.ebi.ac.uk/pub/databases/opentargets/platform/26.03/output/biosample/"
)
_HPO_OBO_URL = "https://raw.githubusercontent.com/obophenotype/human-phenotype-ontology/master/hp.obo"

_HPO_UBERON_CACHE = Path("disease/hpo_uberon_map.json")
_BIOSAMPLE_CACHE = Path("disease/biosample.parquet")
_DISEASE_PHENOTYPE_DIR = Path("disease/phenotype")
_BIOSAMPLE_DIR = Path("disease/biosample")


def _norm_uberon_id(raw: str) -> str:
    """Normalize UBERON ids to OT biosample style (UBERON_0001893)."""
    s = str(raw).strip()
    if s.startswith("UBERON:"):
        return s.replace(":", "_")
    if s.startswith("UBERON_"):
        return s
    return s.replace(":", "_")


def _norm_hp_id(raw: str) -> str:
    s = str(raw).strip()
    if s.startswith("HP:"):
        return s.replace(":", "_")
    return s


async def _ensure_parquet_dir(url: str, local_dir: Path) -> Path:
    """Return first valid parquet in ``local_dir`` (download OT folder if empty)."""
    local_dir.mkdir(parents=True, exist_ok=True)
    valid = [p for p in sorted(local_dir.glob("*.parquet")) if ParquetMaster.is_valid_parquet(p)]
    if valid:
        return valid[0]
    await ParquetMaster.receive_all(ftp_url=url, output_dir=str(local_dir))
    valid = [p for p in sorted(local_dir.glob("*.parquet")) if ParquetMaster.is_valid_parquet(p)]
    if not valid:
        raise FileNotFoundError(f"no valid parquet in {local_dir} for {url}")
    return valid[0]


def _load_hpo_uberon_map() -> dict[str, list[str]]:
    if _HPO_UBERON_CACHE.is_file():
        with open(_HPO_UBERON_CACHE, encoding="utf-8") as f:
            return json.load(f)

    obo_path = Path("disease/hp.obo")
    obo_path.parent.mkdir(parents=True, exist_ok=True)
    if not obo_path.is_file():
        print("downloading HPO OBO for HP->UBERON xrefs...")
        resp = httpx.get(_HPO_OBO_URL, timeout=120, follow_redirects=True)
        resp.raise_for_status()
        obo_path.write_text(resp.text, encoding="utf-8")

    mapping: dict[str, list[str]] = {}
    current_hp: str | None = None
    xref_re = re.compile(r"^xref:\s+UBERON:(\d+)\s*$", re.I)
    term_re = re.compile(r"^id:\s+HP:(\d+)\s*$", re.I)

    with open(obo_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line == "[Term]":
                current_hp = None
                continue
            m_term = term_re.match(line)
            if m_term:
                current_hp = f"HP_{m_term.group(1)}"
                continue
            m_xref = xref_re.match(line)
            if m_xref and current_hp:
                uberon = _norm_uberon_id(f"UBERON:{m_xref.group(1)}")
                mapping.setdefault(current_hp, []).append(uberon)

    for hp_id in mapping:
        mapping[hp_id] = sorted(set(mapping[hp_id]))

    with open(_HPO_UBERON_CACHE, "w", encoding="utf-8") as f:
        json.dump(mapping, f)
    print(f"hpo_uberon_map: {len(mapping)} HP terms with UBERON xref")
    return mapping


def _load_biosample_tree(biosample_path: Path) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """ancestors and descendants per biosample id (UBERON_* included)."""
    ancestors: dict[str, set[str]] = {}
    descendants: dict[str, set[str]] = {}
    pf = pq.ParquetFile(biosample_path)
    for batch in pf.iter_batches(batch_size=5000):
        for row in batch.to_pylist():
            bid = str(row.get("biosampleId") or "")
            if not bid:
                continue
            anc = {_norm_uberon_id(x) for x in (row.get("ancestors") or [])}
            desc = {_norm_uberon_id(x) for x in (row.get("descendants") or [])}
            ancestors[bid] = anc | {bid}
            descendants[bid] = desc | {bid}
    return ancestors, descendants


def _uberon_scope_from_graph(g) -> set[str]:
    """Query-scope UBERON ids from live tissue graph."""
    scope: set[str] = set()
    for nid, attrs in g.G.nodes(data=True):
        if attrs.get("type") == "UBERON_REGION":
            scope.add(_norm_uberon_id(nid))
        elif attrs.get("sub_type") == "anatomy_children":
            scope.add(_norm_uberon_id(nid))
    return scope


def _expand_uberon_scope(scope: set[str], descendants: dict[str, set[str]]) -> set[str]:
    expanded = set(scope)
    for uid in scope:
        expanded |= descendants.get(uid, set())
    return expanded


def _diseases_via_phenotype_uberon(
    phenotype_path: Path,
    scope: set[str],
    hpo_uberon: dict[str, list[str]],
) -> set[str]:
    matched: set[str] = set()
    pf = pq.ParquetFile(phenotype_path)
    for batch in pf.iter_batches(batch_size=10000, columns=["disease", "phenotype"]):
        for row in batch.to_pylist():
            disease_id = row.get("disease")
            hp_raw = row.get("phenotype")
            if not disease_id or not hp_raw:
                continue
            hp_id = _norm_hp_id(hp_raw)
            uberons = hpo_uberon.get(hp_id, [])
            if any(u in scope for u in uberons):
                matched.add(str(disease_id))
    return matched


async def collect_uberon_aligned_disease_ids(g) -> set[str]:
    """
    Diseases linked to query UBERON scope via HPO phenotype -> UBERON xref alignment.
    """
    print("uberon_disease_align: building scope...")
    scope = _uberon_scope_from_graph(g)
    if not scope:
        print("uberon_disease_align: no UBERON scope in graph")
        return set()

    biosample_path = await _ensure_parquet_dir(_BIOSAMPLE_URL, _BIOSAMPLE_DIR)
    _, descendants = _load_biosample_tree(biosample_path)
    expanded_scope = _expand_uberon_scope(scope, descendants)
    print(f"uberon_disease_align: scope {len(scope)} -> expanded {len(expanded_scope)}")

    phenotype_path = await _ensure_parquet_dir(_DISEASE_PHENOTYPE_URL, _DISEASE_PHENOTYPE_DIR)
    hpo_uberon = _load_hpo_uberon_map()
    matched = _diseases_via_phenotype_uberon(phenotype_path, expanded_scope, hpo_uberon)
    print(f"uberon_disease_align: {len(matched)} diseases via HPO->UBERON")
    return matched


def mark_uberon_aligned_diseases(g, disease_ids: set[str]) -> None:
    """Tag diseases that matched UBERON scope for downstream embed filter."""
    for disease_id in disease_ids:
        if not g.G.has_node(disease_id):
            continue
        g.G.nodes[disease_id]["uberon_aligned"] = True
        for uid in _uberon_scope_from_graph(g):
            if g.G.has_node(uid):
                g.add_edge(
                    uid,
                    disease_id,
                    attrs=dict(
                        rel="uberon_phenotype_match",
                        src_layer="TISSUE",
                        trgt_layer="DISEASE",
                    ),
                )
