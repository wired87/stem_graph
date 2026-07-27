"""VEP request building and annotation graph enrichment."""

from __future__ import annotations

import asyncio

from args import CLIENT


def build_vep_request(call):
    host = (
        "grch37.rest.ensembl.org"
        if "37" in str(call.get("GenomeBuild"))
        else "rest.ensembl.org"
    )
    return {
        "url": (
            f"https://{host}/vep/human/region/"
            f"{call['chr']}:{call['MapInfo']}/{call['A']}/{call['B']}"
        ),
        "call_id": call["call_id"],
        "chrom": str(call["chr"]),
        "pos": str(call["MapInfo"]),
        "ref": call["A"],
        "alt": call["B"],
    }


def requests_for_result(graph, result_id):
    calls = [
        attrs
        for _, attrs in graph.get_neighbor_list_rel(
            result_id, trgt_rel="contains_call"
        )
    ]
    return [
        build_vep_request(call)
        for call in calls
        if call.get("genotype_class") != "AA"
    ]


def _add_effect(graph, variant_id, effect, effect_index):
    effect_id = f"{variant_id}:effect:{effect_index}"
    graph.add_node(
        {
            "id": effect_id,
            "type": "VARIANT_EFFECT",
            "index": effect_index,
            "data": effect,
            "impact": effect.get("impact"),
            "consequence_terms": effect.get("consequence_terms", []),
            "amino_acids": effect.get("amino_acids"),
            "protein_start": effect.get("protein_start"),
        }
    )
    graph.add_edge(
        variant_id,
        effect_id,
        attrs={
            "rel": "has_effect",
            "src_layer": "VARIANT",
            "trgt_layer": "VARIANT_EFFECT",
        },
    )
    gene_id = effect.get("gene_id")
    if gene_id:
        graph.add_node(
            {
                "id": gene_id,
                "type": "GENE",
                "name": effect.get("gene_symbol"),
            }
        )
        graph.add_edge(
            effect_id,
            gene_id,
            attrs={
                "rel": "affects_gene",
                "src_layer": "VARIANT_EFFECT",
                "trgt_layer": "GENE",
            },
        )
    proteins = set()
    for key in ("swissprot", "trembl", "uniprot"):
        value = effect.get(key)
        if isinstance(value, str):
            proteins.update(value.split(","))
        elif isinstance(value, list):
            proteins.update(value)
    for accession in filter(None, proteins):
        graph.add_node(
            {"id": accession, "type": "PROTEIN", "accession": accession}
        )
        graph.add_edge(
            effect_id,
            accession,
            attrs={
                "rel": "affects_protein",
                "src_layer": "VARIANT_EFFECT",
                "trgt_layer": "PROTEIN",
            },
        )


def _materialize_annotation(graph, request, payload, error):
    variant_id = payload.get("id") or (
        f"{request['chrom']}:{request['pos']}:{request['ref']}>{request['alt']}"
    )
    graph.add_node(
        {
            "id": variant_id,
            "type": "VARIANT",
            "chrom": request["chrom"],
            "position": request["pos"],
            "reference": request["ref"],
            "alternate": request["alt"],
            "most_severe_consequence": payload.get("most_severe_consequence"),
            "annotation_status": "failed" if error else "complete",
            "annotation_error": error,
            "annotation": payload,
        }
    )
    graph.add_edge(
        request["call_id"],
        variant_id,
        attrs={
            "rel": "calls_variant",
            "src_layer": "VARIANT_CALL",
            "trgt_layer": "VARIANT",
        },
    )
    for index, effect in enumerate(payload.get("transcript_consequences", [])):
        _add_effect(graph, variant_id, effect, index)
    return payload


async def fetch_annotations(graph, requests, concurrency=8, client=CLIENT):
    semaphore = asyncio.Semaphore(concurrency)

    async def fetch(request):
        try:
            async with semaphore:
                response = await client.get(
                    request["url"], headers={"Accept": "application/json"}
                )
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, list):
                    payload = payload[0] if payload else {}
                return request, payload, None
        except Exception as exc:
            return request, {}, str(exc)

    fetched = await asyncio.gather(*(fetch(item) for item in requests))
    return [
        _materialize_annotation(graph, request, payload, error)
        for request, payload, error in fetched
    ]


def annotate_result(graph, result_id, concurrency=8, client=CLIENT):
    requests = requests_for_result(graph, result_id)
    return asyncio.run(
        fetch_annotations(graph, requests, concurrency=concurrency, client=client)
    )
