"""
DrugBank drug–drug interaction lookup (local export + ChEMBL drug warnings fallback).

Prompt: infer valuable drug stacks under drug-drug interaction — DrugBank in drug dir.
Place licensed DrugBank DDI export at data/drugbank_ddi.csv or set DRUGBANK_DDI_PATH.
Columns: drug_a,drug_b,severity,description (DrugBank ids or ChEMBL ids).
"""
from __future__ import annotations

import csv
import os
from pathlib import Path

from core.app_utils import AsyncApiFetcher

# CHAR: default local DDI table (user-provided DrugBank export)
_DEFAULT_DDI_PATH = Path("data/drugbank_ddi.csv")
_SEVERITY_RANK = {"major": 3, "moderate": 2, "minor": 1, "unknown": 0}


def _norm_id(raw: str) -> str:
    return str(raw).strip().upper()


def _extract_drugbank_ids(attrs: dict) -> set[str]:
    """DrugBank ids from ChEMBL molecule cross_references on graph node."""
    ids: set[str] = set()
    for key in ("drugbank_id", "drugbank_ids"):
        val = attrs.get(key)
        if val:
            ids.add(_norm_id(str(val).replace("DB", "DB")))
    xrefs = attrs.get("cross_references") or attrs.get("molecule_cross_references") or []
    if isinstance(xrefs, list):
        for xref in xrefs:
            if not isinstance(xref, dict):
                continue
            src = str(xref.get("xref_src") or xref.get("source") or "").lower()
            if "drugbank" in src:
                xid = xref.get("xref_id") or xref.get("xref")
                if xid:
                    ids.add(_norm_id(str(xid)))
    return ids


def _chembl_id_from_attrs(attrs: dict, nid: str) -> str:
    return _norm_id(attrs.get("molecule_chembl_id") or attrs.get("id") or nid)


class DrugBankDDIIndex:
    """In-memory pair index keyed by normalized drug id tuples."""

    def __init__(self) -> None:
        self._pairs: dict[frozenset[str], dict] = {}

    def add(self, drug_a: str, drug_b: str, severity: str, description: str, source: str) -> None:
        a, b = _norm_id(drug_a), _norm_id(drug_b)
        if not a or not b or a == b:
            return
        key = frozenset({a, b})
        rank = _SEVERITY_RANK.get(severity.lower(), 0)
        prev = self._pairs.get(key)
        if prev and prev.get("rank", 0) >= rank:
            return
        self._pairs[key] = {
            "severity": severity.lower(),
            "rank": rank,
            "description": description[:240],
            "source": source,
        }

    def lookup(self, id_a: str, id_b: str) -> dict | None:
        return self._pairs.get(frozenset({_norm_id(id_a), _norm_id(id_b)}))

    def lookup_any_ids(self, ids_a: set[str], ids_b: set[str]) -> dict | None:
        for a in ids_a:
            for b in ids_b:
                hit = self.lookup(a, b)
                if hit:
                    return hit
        return None


def load_drugbank_ddi_csv(path: Path) -> DrugBankDDIIndex:
    index = DrugBankDDIIndex()
    if not path.is_file():
        return index
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            index.add(
                row.get("drug_a") or row.get("drugbank_id_a") or "",
                row.get("drug_b") or row.get("drugbank_id_b") or "",
                row.get("severity") or "unknown",
                row.get("description") or "",
                "drugbank_csv",
            )
    print(f"drugbank_ddi: loaded {len(index._pairs)} pairs from {path}")
    return index


class ChemblWarningFetcher(AsyncApiFetcher):
    """ChEMBL drug_warning fallback when no local DrugBank DDI file."""

    BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"
    DEFAULT_HEADERS = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (acid_master)",
    }
    RATE_LIMIT = 6

    async def warnings_for_molecule(self, molecule_chembl_id: str) -> list[dict]:
        url = f"{self.BASE_URL}/drug_warning.json"
        params = {"molecule_chembl_id": molecule_chembl_id, "format": "json"}
        data = await self._execute_get(url, params=params)
        return data.get("drug_warnings") or []


async def build_ddi_index(g, molecule_ids: list[str]) -> DrugBankDDIIndex:
    """Load DrugBank CSV + enrich from ChEMBL warnings for in-graph molecules."""
    ddi_path = Path(os.environ.get("DRUGBANK_DDI_PATH", str(_DEFAULT_DDI_PATH)))
    index = load_drugbank_ddi_csv(ddi_path)

    # CHAR: ChEMBL warnings only when local DrugBank table is empty or thin
    if len(index._pairs) < 50:
        fetcher = ChemblWarningFetcher()
        for nid in molecule_ids[:12]:
            attrs = g.G.nodes.get(nid, {})
            chembl = _chembl_id_from_attrs(attrs, nid)
            try:
                warnings = await fetcher.warnings_for_molecule(chembl)
            except Exception as exc:
                print(f"drugbank_ddi: ChEMBL warning skip {chembl}: {exc}")
                continue
            for w in warnings:
                desc = w.get("description") or w.get("warning_type") or ""
                severity = "moderate" if "interaction" in desc.lower() else "minor"
                # CHAR: pair warnings across molecules sharing warning_class
                wclass = w.get("warning_class") or w.get("warning_type") or ""
                if wclass:
                    index.add(chembl, f"CLASS::{wclass}", severity, desc, "chembl_warning")

    return index


def molecule_id_sets(g, nid: str, attrs: dict) -> set[str]:
    """All ids usable for DDI lookup (ChEMBL + DrugBank)."""
    ids = {_chembl_id_from_attrs(attrs, nid)}
    ids |= _extract_drugbank_ids(attrs)
    return ids


def pair_ddi_severity(
    index: DrugBankDDIIndex,
    g,
    nid_a: str,
    nid_b: str,
) -> dict | None:
    attrs_a = g.G.nodes.get(nid_a, {})
    attrs_b = g.G.nodes.get(nid_b, {})
    return index.lookup_any_ids(molecule_id_sets(g, nid_a, attrs_a), molecule_id_sets(g, nid_b, attrs_b))
