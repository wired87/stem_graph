"""
Open Targets disease parquet uptake into the live graph.

Prompt: analyze and run the run_query_pipe workflow — fix corrupt local parquet stubs.
Prompt: implement disease embedding reduction — uptake nodes only; embed filtered subset via cache.
"""
from __future__ import annotations

import sys
from pathlib import Path

# CHAR: repo root on sys.path when this file is run as a script.
for _p in Path(__file__).resolve().parents:
    if (_p / "core").is_dir() and (_p / "embedder").is_dir():
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        break

import os

from disease.disease_emb_cache import embed_diseases_with_cache
from firegraph.file.parquet import ParquetMaster

# CHAR: OT platform disease export directory (not a single file URL)
DISEASE_OT_URL = "http://ftp.ebi.ac.uk/pub/databases/opentargets/platform/26.03/output/disease/"


def _as_list(val) -> list:
    """Normalize parquet list columns (list, ndarray, None) without ambiguous truth tests."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, tuple):
        return list(val)
    # CHAR: pandas may yield numpy.ndarray for list columns — never use ``val or []``
    if hasattr(val, "tolist"):
        return list(val.tolist())
    return [val]


async def _ensure_disease_parquets(local_dir: Path) -> list[Path]:
    """Download OT disease parquets when missing or corrupt."""
    local_dir.mkdir(parents=True, exist_ok=True)
    for stale in local_dir.glob("*.parquet"):
        if not ParquetMaster.is_valid_parquet(stale):
            print(f"removing invalid parquet: {stale}")
            stale.unlink()
    valid = [p for p in sorted(local_dir.glob("*.parquet")) if ParquetMaster.is_valid_parquet(p)]
    if not valid:
        await ParquetMaster.receive_all(
            ftp_url=DISEASE_OT_URL,
            output_dir=str(local_dir),
        )
        valid = [p for p in sorted(local_dir.glob("*.parquet")) if ParquetMaster.is_valid_parquet(p)]
    if not valid:
        raise FileNotFoundError(f"no valid Open Targets disease parquet in {local_dir}")
    return valid


async def uptake_open_targets_diseases_phenotypes(
    g,
    batch_size: int = 10000,
    only_ids: set[str] | None = None,
):
    print("process_open_targets_diseases...")
    local_dir = Path(os.path.abspath("disease"))
    parquet_files = await _ensure_disease_parquets(local_dir)

    print("creating disease nodes...")

    hierarchy = {
        "parents": "has_parent",
        "children": "has_child",
        "ancestors": "has_ancestor",
        "descendants": "has_descendant",
        "therapeuticAreas": "belongs_to",
    }

    total_rows = 0

    for parquet_file in parquet_files:
        parqmaster = ParquetMaster(str(parquet_file))
        parqmaster.read(return_dict=False, print_specs=True)

        for batch in parqmaster.iter_batches(batch_size):
            df = batch.to_pandas()

            for row in df.to_dict("records"):
                total_rows += 1

                disease_id = row.get("id")
                if not disease_id:
                    continue
                if only_ids is not None and disease_id not in only_ids:
                    continue

                synonyms = []
                synonym_fields = [
                    "exactSynonyms",
                    "relatedSynonyms",
                    "narrowSynonyms",
                    "broadSynonyms",
                ]
                for field in synonym_fields:
                    synonyms.extend(_as_list(row.get(field)))

                syn_struct = row.get("synonyms")
                if isinstance(syn_struct, dict):
                    for key in (
                        "hasExactSynonym",
                        "hasRelatedSynonym",
                        "hasNarrowSynonym",
                        "hasBroadSynonym",
                    ):
                        synonyms.extend(_as_list(syn_struct.get(key)))

                synonyms = sorted(set(str(x).strip() for x in synonyms if x))

                ontology = row.get("ontology") or {}
                source = ontology.get("sources") or {}

                embed_parts = []
                for value in (row.get("name"), row.get("description")):
                    if value:
                        embed_parts.append(str(value))
                if synonyms:
                    embed_parts.append("Synonyms: " + ", ".join(synonyms))
                ta = _as_list(row.get("therapeuticAreas"))
                if ta:
                    embed_parts.append("Therapeutic Areas: " + ", ".join(str(x) for x in ta))
                embed_content = "\n".join(embed_parts)

                node = dict(
                    id=disease_id,
                    type="DISEASE",
                    name=row.get("name"),
                    code=row.get("code"),
                    description=row.get("description"),
                    synonyms=synonyms,
                    therapeutic_areas=_as_list(row.get("therapeuticAreas")),
                    is_leaf=ontology.get("leaf"),
                    is_therapeutic_area=ontology.get("isTherapeuticArea"),
                    ontology_source_name=source.get("name"),
                    ontology_source_url=source.get("url"),
                    embed_key="text",
                    text=embed_content,
                )
                g.add_node(node)

                for col, rel in hierarchy.items():
                    for other_id in _as_list(row.get(col)):
                        g.add_node(dict(id=other_id, type="DISEASE"))
                        g.add_edge(
                            src=disease_id,
                            trgt=other_id,
                            attrs=dict(
                                rel=rel,
                                src_layer="DISEASE",
                                trgt_layer="DISEASE",
                            ),
                        )

    print(f"process_open_targets_diseases done ({total_rows} rows ingested).")


async def embed_filtered_diseases(
    g,
    embed_ids: set[str] | None = None,
) -> int:
    """Embed only selected DISEASE nodes using persistent cache (batch missing only)."""
    if embed_ids is None:
        embed_ids = {
            nid
            for nid, attrs in g.G.nodes(data=True)
            if attrs.get("type") == "DISEASE"
        }
    print(f"embed_filtered_diseases: {len(embed_ids)} candidates")
    return embed_diseases_with_cache(g, disease_ids=embed_ids)


async def uptake_and_embed_diseases_for_query(g) -> None:
    """
    UBERON-aligned + protein-linked disease subset only; embed via persistent cache.
    """
    from disease.score_disease_trgt import (
        collect_association_disease_ids,
        protein_linked_disease_ids,
        score_disease_trgt,
    )
    from disease.uberon_disease_align import (
        collect_uberon_aligned_disease_ids,
        mark_uberon_aligned_diseases,
    )

    uberon_ids = await collect_uberon_aligned_disease_ids(g)
    association_ids = await collect_association_disease_ids(g)
    uptake_ids = uberon_ids | association_ids
    print(f"disease uptake filter: uberon={len(uberon_ids)} association={len(association_ids)}")

    if not uptake_ids:
        print("disease uptake: no candidates — skip")
        return

    await uptake_open_targets_diseases_phenotypes(g, only_ids=uptake_ids)
    mark_uberon_aligned_diseases(g, uberon_ids)
    await score_disease_trgt(g)

    embed_ids = set(uberon_ids) | protein_linked_disease_ids(g)
    await embed_filtered_diseases(g, embed_ids=embed_ids)


if __name__ == "__main__":
    # Prompt: standalone query_pipe check — hardcoded GUtils fixture for uptake_and_embed_diseases_for_query.
    import sys
    from pathlib import Path
    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    import asyncio
    from embedder import embed_batch
    from firegraph.graph.local_graph_utils import GUtils

    async def _check_uptake_and_embed_diseases_for_query():
        # CHAR: UBERON tissue + in-graph gene/protein targets for association + uberon filter paths.
        g = GUtils()
        tissue_vec = embed_batch(["Thalamus"])[0].tolist()
        g.add_node(
            attrs=dict(
                id="UBERON_0001896",
                type="TISSUE",
                sub_type="UBERON",
                description="Thalamus",
                embed_key="description",
                embedding=tissue_vec,
            )
        )
        g.add_node(attrs=dict(id="ENSG00000136531", type="GENE", name="SCN1A"))
        g.add_node(attrs=dict(id="P35498", type="PROTEIN", name="SCN1A", genes=["SCN1A"]))
        g.add_edge(
            "ENSG00000136531",
            "P35498",
            attrs=dict(rel="encodes", src_layer="GENE", trgt_layer="PROTEIN"),
        )
        n0 = g.G.number_of_nodes()
        await uptake_and_embed_diseases_for_query(g)
        diseases = [nid for nid, a in g.G.nodes(data=True) if a.get("type") == "DISEASE"]
        embedded = [
            nid for nid, a in g.G.nodes(data=True)
            if a.get("type") == "DISEASE" and a.get("embedding") is not None
        ]
        print(
            f"[__main__] uptake_and_embed_diseases_for_query OK  "
            f"diseases={len(diseases)} embedded={len(embedded)} nodes+={g.G.number_of_nodes()-n0}"
        )

    asyncio.run(_check_uptake_and_embed_diseases_for_query())
