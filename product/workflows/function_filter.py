"""Optional GO-term based functional filter for the StemGraph pipeline."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping

import numpy as np

from args import CLIENT


GO_PATTERN = re.compile(r"GO:\d{7}", re.IGNORECASE)


def protein_workflow_config(cfg):
    """Normalize top-level or ``protein``-nested workflow configuration."""
    if not isinstance(cfg, Mapping):
        return {}
    protein_cfg = cfg.get("protein", cfg)
    return protein_cfg if isinstance(protein_cfg, Mapping) else {}


def function_filter_enabled(cfg):
    params = protein_workflow_config(cfg)
    functions = params.get("functional_annotation", params.get("functions"))
    return bool(functions)


def _as_function_list(cfg):
    params = protein_workflow_config(cfg)
    functions = params.get("functional_annotation", params.get("functions", []))
    if isinstance(functions, str):
        return [functions]
    return [str(item) for item in functions if item]


def _gene_entries(graph, cfg):
    params = protein_workflow_config(cfg)
    configured = params.get("ensembl_entries", {})
    if isinstance(configured, list):
        configured = {
            str(item.get("id") or item.get("gene_id")): item
            for item in configured
            if isinstance(item, Mapping)
            and (item.get("id") or item.get("gene_id"))
        }
    if not isinstance(configured, Mapping):
        configured = {}

    entries = []
    for gene_id, attrs in graph.G.nodes(data=True):
        if attrs.get("type") != "GENE":
            continue
        merged = dict(attrs)
        if isinstance(configured.get(gene_id), Mapping):
            merged.update(configured[gene_id])
        entries.append((gene_id, merged))
    return entries


def _extract_go_rows(value):
    """Recursively extract GO identifiers and useful labels from Ensembl data."""
    rows = {}

    def visit(item):
        if isinstance(item, Mapping):
            candidates = (
                item.get("primary_id"),
                item.get("display_id"),
                item.get("id"),
                item.get("go_id"),
                item.get("accession"),
            )
            go_id = next(
                (
                    match.group(0).upper()
                    for candidate in candidates
                    if candidate
                    for match in [GO_PATTERN.search(str(candidate))]
                    if match
                ),
                None,
            )
            if go_id:
                rows.setdefault(
                    go_id,
                    {
                        "id": go_id,
                        "name": item.get("display_id") or item.get("name"),
                        "definition": (
                            item.get("description")
                            or item.get("definition")
                            or item.get("name")
                            or go_id
                        ),
                    },
                )
            for nested in item.values():
                visit(nested)
        elif isinstance(item, (list, tuple, set)):
            for nested in item:
                visit(nested)
        elif isinstance(item, str):
            for match in GO_PATTERN.finditer(item):
                go_id = match.group(0).upper()
                rows.setdefault(
                    go_id,
                    {"id": go_id, "name": go_id, "definition": go_id},
                )

    visit(value)
    return rows


async def _fetch_gene_go_xrefs(gene_ids, client, concurrency):
    semaphore = asyncio.Semaphore(concurrency)

    async def fetch(gene_id):
        try:
            async with semaphore:
                response = await client.get(
                    f"https://rest.ensembl.org/xrefs/id/{gene_id}",
                    params={"external_db": "GO", "all_levels": 1},
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                return gene_id, response.json(), None
        except Exception as exc:
            return gene_id, [], str(exc)

    return await asyncio.gather(*(fetch(gene_id) for gene_id in gene_ids))


def collect_gene_go_terms(graph, cfg, client=CLIENT):
    """
    Build canonical GO and gene-to-GO index nodes.

    Gene order is stored explicitly and is shared by ``gene_to_goterm`` and
    ``goterm_gene_alignment``.
    """
    params = protein_workflow_config(cfg)
    genes = _gene_entries(graph, cfg)
    gene_rows = {gene_id: _extract_go_rows(entry) for gene_id, entry in genes}
    missing = [gene_id for gene_id, rows in gene_rows.items() if not rows]
    if missing and params.get("fetch_go_xrefs", True):
        fetched = asyncio.run(
            _fetch_gene_go_xrefs(
                missing,
                client=client,
                concurrency=int(params.get("go_fetch_concurrency", 8)),
            )
        )
        for gene_id, payload, error in fetched:
            gene_rows[gene_id].update(_extract_go_rows(payload))
            graph.update_node(
                {
                    "id": gene_id,
                    "go_xref_status": "failed" if error else "complete",
                    "go_xref_error": error,
                }
            )

    go_ids = sorted(
        {
            go_id
            for rows in gene_rows.values()
            for go_id in rows
        }
    )
    all_rows = {}
    for rows in gene_rows.values():
        for go_id, row in rows.items():
            all_rows.setdefault(go_id, row)
    goterm_data = [
        {"idx": idx, **all_rows[go_id]}
        for idx, go_id in enumerate(go_ids)
    ]
    index_by_id = {row["id"]: row["idx"] for row in goterm_data}
    gene_ids = [gene_id for gene_id, _ in genes]
    gene_to_goterm = [
        sorted(index_by_id[go_id] for go_id in gene_rows[gene_id])
        for gene_id in gene_ids
    ]

    graph.add_node(
        {
            "id": "goterm",
            "type": "GO_TERM",
            "data": goterm_data,
            "index_by_id": index_by_id,
        }
    )
    graph.add_node(
        {
            "id": "gene_to_goterm",
            "type": "GENE_TO_GOTERM",
            "genes": gene_ids,
            "data": gene_to_goterm,
        }
    )
    return goterm_data, gene_ids, gene_to_goterm


def align_goterms_to_functions(graph, cfg, embed_batch_fn=None):
    """Align configured functions to canonical GO rows with cosine similarity."""
    if embed_batch_fn is None:
        from embedder import embed_batch as embed_batch_fn

    functions = _as_function_list(cfg)
    params = protein_workflow_config(cfg)
    threshold = float(
        params.get(
            "function_similarity_threshold",
            params.get("similarity_threshold", 0.75),
        )
    )
    goterm_data = graph.get_node("goterm")["data"]
    # A GO accession alone has no lexical biological meaning.  Do not feed
    # bare IDs into a text embedder; retain their canonical indices but only
    # align rows for which Ensembl/configuration supplied descriptive text.
    labelled_terms = []
    for row in goterm_data:
        label = row.get("definition") or row.get("name")
        if label and str(label).strip().upper() != row["id"]:
            labelled_terms.append((row["idx"], str(label)))
    by_function = [[] for _ in functions]
    score_rows = [[] for _ in functions]
    aligned = set()

    if functions and labelled_terms:
        function_vectors = np.asarray(embed_batch_fn(functions), dtype=np.float32)
        goterm_vectors = np.asarray(
            embed_batch_fn([label for _, label in labelled_terms]),
            dtype=np.float32,
        )
        function_norms = np.linalg.norm(function_vectors, axis=1, keepdims=True)
        goterm_norms = np.linalg.norm(goterm_vectors, axis=1, keepdims=True)
        function_vectors = function_vectors / np.maximum(function_norms, 1e-12)
        goterm_vectors = goterm_vectors / np.maximum(goterm_norms, 1e-12)
        scores = function_vectors @ goterm_vectors.T
        for function_idx, row in enumerate(scores):
            for local_idx, score in enumerate(row):
                if float(score) > threshold:
                    goterm_idx = labelled_terms[local_idx][0]
                    by_function[function_idx].append(goterm_idx)
                    score_rows[function_idx].append(
                        {"goterm_idx": goterm_idx, "score": float(score)}
                    )
                    aligned.add(goterm_idx)

    graph.add_node(
        {
            "id": "goterm_function_alignment",
            "type": "GOTERM_FUNCTION_ALIGNMENT",
            "functions": functions,
            "threshold": threshold,
            "data": sorted(aligned),
            "by_function": by_function,
            "scores": score_rows,
            "method": "cosine_similarity_of_text_embeddings",
            "unlabelled_goterm_indices": sorted(
                set(range(len(goterm_data)))
                - {idx for idx, _ in labelled_terms}
            ),
        }
    )
    return sorted(aligned)


def align_genes_to_functions(graph):
    """Create the requested 0/None gene mask in gene order."""
    mapping = graph.get_node("gene_to_goterm")
    aligned = set(graph.get_node("goterm_function_alignment")["data"])
    mask = [
        0 if any(goterm_idx in aligned for goterm_idx in term_indices) else None
        for term_indices in mapping["data"]
    ]
    graph.add_node(
        {
            "id": "goterm_gene_alignment",
            "type": "GOTERM_GENE_ALIGNMENT",
            "genes": list(mapping["genes"]),
            "data": mask,
        }
    )
    return mask


def run_function_filter(graph, cfg, client=CLIENT, embed_batch_fn=None):
    collect_gene_go_terms(graph, cfg, client=client)
    align_goterms_to_functions(graph, cfg, embed_batch_fn=embed_batch_fn)
    return align_genes_to_functions(graph)
