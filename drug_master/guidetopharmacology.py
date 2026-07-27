"""
Guide to Pharmacology (IUPHAR) — ligand–target validation + electrophysiology refs.

Prompt: include guidetopharmacology for disease-drug prediction and electrophysiological data.
"""
from __future__ import annotations

import json
from pathlib import Path

from core.app_utils import AsyncApiFetcher

_GTOP_BASE = "https://www.guidetopharmacology.org/services"
_CACHE_PATH = Path("data/gtop_validation_cache.json")


class GtoPdbFetcher(AsyncApiFetcher):
    BASE_URL = _GTOP_BASE
    DEFAULT_HEADERS = {"Accept": "application/json", "User-Agent": "acid_master"}
    RATE_LIMIT = 8

    async def targets_for_uniprot(self, uniprot_id: str) -> list[dict]:
        url = f"{self.BASE_URL}/targets"
        params = {"database": "UniProtKB", "database_id": uniprot_id}
        data = await self._execute_get(url, params=params)
        return data if isinstance(data, list) else []

    async def ligands_by_name(self, name: str) -> list[dict]:
        url = f"{self.BASE_URL}/ligands"
        params = {"name": name}
        data = await self._execute_get(url, params=params)
        return data if isinstance(data, list) else []

    async def ligand_interactions(self, ligand_id: int) -> list[dict]:
        url = f"{self.BASE_URL}/ligands/{ligand_id}/interactions"
        data = await self._execute_get(url)
        return data if isinstance(data, list) else []


def _load_cache() -> dict:
    if _CACHE_PATH.is_file():
        with open(_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _write_cache(cache: dict) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f)


async def validate_molecule_on_targets(
    g,
    molecule_nid: str,
    protein_ids: set[str],
    fetcher: GtoPdbFetcher | None = None,
) -> dict:
    """
  Lightweight GtoP check: ligand name -> interactions at graph UniProt targets.
  Returns validation summary (no extra graph nodes).
    """
    attrs = g.G.nodes.get(molecule_nid, {})
    name = attrs.get("pref_name") or attrs.get("name") or molecule_nid
    cache = _load_cache()
    cache_key = f"{molecule_nid}::{name}"
    if cache_key in cache:
        return cache[cache_key]

    fetcher = fetcher or GtoPdbFetcher()
    ligands = await fetcher.ligands_by_name(str(name))
    if not ligands:
        result = {"validated": False, "ligand_id": None, "matched_targets": [], "actions": []}
        cache[cache_key] = result
        _write_cache(cache)
        return result

    ligand_id = ligands[0].get("ligandId")
    if not ligand_id:
        result = {"validated": False, "ligand_id": None, "matched_targets": [], "actions": []}
        cache[cache_key] = result
        _write_cache(cache)
        return result

    interactions = await fetcher.ligand_interactions(int(ligand_id))
    gtop_target_ids: set[int] = set()
    for pid in protein_ids:
        try:
            targets = await fetcher.targets_for_uniprot(pid)
        except Exception:
            continue
        for t in targets:
            tid = t.get("targetId")
            if tid:
                gtop_target_ids.add(int(tid))

    matched: list[dict] = []
    actions: list[str] = []
    for inter in interactions:
        tid = inter.get("targetId")
        if tid and int(tid) in gtop_target_ids:
            matched.append({
                "target_id": tid,
                "target_name": inter.get("targetName"),
                "action": inter.get("action"),
                "affinity": inter.get("affinity"),
                "affinity_type": inter.get("affinityType"),
                "pubmed_id": inter.get("pubmedId"),
            })
            act = inter.get("action")
            if act:
                actions.append(str(act))

    result = {
        "validated": len(matched) > 0,
        "ligand_id": ligand_id,
        "matched_targets": matched[:6],
        "actions": sorted(set(actions)),
        "source": "guidetopharmacology.org",
    }
    cache[cache_key] = result
    _write_cache(cache)
    return result
