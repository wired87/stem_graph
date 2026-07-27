"""Live research evidence acquisition for the precision drug graph."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode
from urllib.request import Request, urlopen


CHEMBL = "https://www.ebi.ac.uk/chembl/api/data"
OMNIPATH = "https://omnipathdb.org/interactions/"
ACTIVE_MECHANISMS = {
    "AGONIST", "ACTIVATOR", "STIMULATOR", "POSITIVE ALLOSTERIC MODULATOR",
    "PARTIAL AGONIST", "INHIBITOR", "ANTAGONIST", "BLOCKER",
    "NEGATIVE ALLOSTERIC MODULATOR", "INVERSE AGONIST",
}


def _get_json(url: str, params: dict, timeout: float = 60.0):
    query = urlencode({
        key: value for key, value in params.items() if value is not None
    })
    request = Request(
        f"{url}?{query}",
        headers={"Accept": "application/json", "User-Agent": "CNVMaster-research/1.0"},
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_chembl_targets(accession: str) -> tuple[str, list[dict]]:
    payload = _get_json(
        f"{CHEMBL}/target.json",
        {
            "target_components__accession": accession,
            "target_organism": "Homo sapiens",
            "limit": 50,
        },
    )
    rows = [
        row for row in payload.get("targets", [])
        if row.get("target_chembl_id")
    ]
    return accession, rows


def fetch_targets(accessions: list[str]) -> dict[str, list[dict]]:
    output = {accession: [] for accession in accessions}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(fetch_chembl_targets, accession): accession
            for accession in accessions
        }
        for future in as_completed(futures):
            accession = futures[future]
            try:
                key, rows = future.result()
                output[key] = rows
            except Exception as exc:
                print(f"ChEMBL target lookup failed for {accession}: {exc}")
    return output


def fetch_omnipath_depth(
    accessions: list[str],
    max_depth: int = 10,
    max_nodes: int = 1500,
) -> dict[str, list[dict]]:
    """Breadth-first OmniPath expansion with a hard graph-size safety cap."""
    seeds = set(accessions)
    frontier = set(accessions)
    seen = set(accessions)
    rows_by_key: dict[tuple[str, str], dict] = {}

    for depth in range(1, max_depth + 1):
        if not frontier or len(seen) >= max_nodes:
            break
        payload = []
        frontier_ids = sorted(frontier)
        for offset in range(0, len(frontier_ids), 100):
            batch = _get_json(
                OMNIPATH,
                {
                    "partners": ",".join(frontier_ids[offset:offset + 100]),
                    "datasets": "omnipath,pathwayextra",
                    "fields": "sources,references",
                    "format": "json",
                },
                timeout=120.0,
            )
            if not isinstance(batch, list):
                raise RuntimeError("Unexpected OmniPath response type")
            if batch and not isinstance(batch[0], dict):
                raise RuntimeError(f"OmniPath API error: {batch}")
            payload.extend(batch)
        next_frontier = set()
        for row in payload:
            source = str(row.get("source") or "").strip()
            target = str(row.get("target") or "").strip()
            if not source or not target:
                continue
            enriched = {**row, "dims": depth, "source": source, "target": target}
            rows_by_key[(source, target)] = enriched
            for node_id in (source, target):
                if node_id not in seen and len(seen) + len(next_frontier) < max_nodes:
                    next_frontier.add(node_id)
        seen.update(next_frontier)
        frontier = next_frontier
        print(
            f"OmniPath depth {depth}: interactions={len(rows_by_key)}, "
            f"proteins={len(seen)}"
        )

    rows = list(rows_by_key.values())
    return {seed: rows for seed in seeds}


def _best_activity(molecule_id: str, target_id: str) -> dict | None:
    payload = _get_json(
        f"{CHEMBL}/activity.json",
        {
            "molecule_chembl_id": molecule_id,
            "target_chembl_id": target_id,
            "target_organism": "Homo sapiens",
            "standard_type__in": "IC50,EC50,Ki,Kd",
            "limit": 100,
        },
    )
    candidates = []
    for row in payload.get("activities", []):
        value = row.get("standard_value")
        unit = row.get("standard_units")
        if value is None or unit not in {"M", "mM", "uM", "µM", "nM", "pM"}:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if numeric > 0:
            candidates.append((numeric, row))
    return min(candidates, key=lambda item: item[0])[1] if candidates else None


def fetch_candidates_for_target(target_id: str) -> tuple[str, list[dict]]:
    payload = _get_json(
        f"{CHEMBL}/mechanism.json",
        {"target_chembl_id": target_id, "limit": 100},
    )
    candidates = []
    seen = set()
    for mechanism in payload.get("mechanisms", []):
        molecule_id = mechanism.get("molecule_chembl_id")
        action = str(mechanism.get("action_type") or "").upper()
        if not molecule_id or molecule_id in seen or action not in ACTIVE_MECHANISMS:
            continue
        seen.add(molecule_id)
        try:
            activity = _best_activity(molecule_id, target_id)
        except Exception as exc:
            print(f"ChEMBL activity lookup failed for {molecule_id}/{target_id}: {exc}")
            continue
        if not activity:
            continue
        candidates.append({
            "molecule_chembl_id": molecule_id,
            "target_chembl_id": target_id,
            "mechanism": action.lower(),
            "mechanism_of_action": mechanism.get("mechanism_of_action"),
            "activity_value": float(activity["standard_value"]),
            "activity_unit": activity["standard_units"],
            "activity_type": activity.get("standard_type"),
            "confidence": min(
                1.0, max(0.0, float(activity.get("confidence_score") or 5) / 9.0)
            ),
            "selectivity": 1.0,
            "max_phase": mechanism.get("max_phase"),
            "source": "ChEMBL",
        })
    return target_id, candidates


def fetch_drug_candidates(target_records: dict[str, list[dict]]) -> dict[str, list[dict]]:
    target_ids = sorted({
        row["target_chembl_id"]
        for rows in target_records.values()
        for row in rows
        if row.get("target_chembl_id")
    })
    output = {target_id: [] for target_id in target_ids}
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(fetch_candidates_for_target, target_id): target_id
            for target_id in target_ids
        }
        for future in as_completed(futures):
            target_id = futures[future]
            try:
                key, rows = future.result()
                output[key] = rows
                print(f"ChEMBL candidates {key}: {len(rows)}")
            except Exception as exc:
                print(f"ChEMBL mechanism lookup failed for {target_id}: {exc}")
    return output


def collect_live_evidence(accessions: list[str], max_depth: int = 10) -> dict:
    targets = fetch_targets(accessions)
    target_count = len({
        row.get("target_chembl_id")
        for rows in targets.values()
        for row in rows
    })
    print(f"ChEMBL targets: {target_count}")
    pathways = fetch_omnipath_depth(accessions, max_depth=max_depth)
    candidates = fetch_drug_candidates(targets)
    return {
        "target_records": targets,
        "pathway_rows": pathways,
        "candidates_by_target": candidates,
        "vep_annotations": [],
    }
