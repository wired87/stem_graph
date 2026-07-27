"""IDAT alignment, genotype calling and per-index graph materialization."""

from __future__ import annotations

from product.calculations import filter_strongest_signal
from product.stem_file.read_idat import read_idat_data
from .inputs import single_file


def align_ids(gids, rids, egt_addresses, manifest):
    red = {int(address): idx for idx, address in enumerate(rids)}
    green = {int(address): idx for idx, address in enumerate(gids)}
    egt = {int(address): idx for idx, address in enumerate(egt_addresses)}
    aligned = []
    for raw_address in manifest.addresses:
        address = int(raw_address)
        red_idx = red.get(address, -1)
        green_idx = green.get(address, -1)
        egt_idx = egt.get(address, -1)
        aligned.append(
            (-1, -1, -1)
            if (red_idx < 0 and green_idx < 0) or egt_idx < 0
            else (red_idx, green_idx, egt_idx)
        )
    return aligned


def _sample_node(graph, green_attrs):
    meta = green_attrs["meta"]
    sample_id = f"sample:{meta.get('chip_name')}:{meta.get('chip_pos')}"
    graph.add_node(
        {
            "id": sample_id,
            "type": "SAMPLE",
            "chip_name": meta.get("chip_name"),
            "chip_pos": meta.get("chip_pos"),
            "array_name": meta.get("array_name"),
            "genome_version": meta.get("genome_version"),
        }
    )
    return sample_id


def _materialize_calls(graph, result_id, calls, manifest_rows):
    for call in calls:
        call_id = f"{result_id}:call:{call['manifest_idx']}"
        call["call_id"] = call_id
        raw_columns = (
            manifest_rows[call["manifest_idx"]]
            if call["manifest_idx"] < len(manifest_rows)
            else {}
        )
        graph.add_node(
            {
                "id": call_id,
                "type": "VARIANT_CALL",
                "index": call["manifest_idx"],
                "columns": {**raw_columns, **call},
                "manifest_columns": raw_columns,
                **call,
            }
        )
        graph.add_edge(
            result_id,
            call_id,
            attrs={
                "rel": "contains_call",
                "src_layer": "SCORE_RESULT",
                "trgt_layer": "VARIANT_CALL",
                "index": call["manifest_idx"],
            },
        )


def build_calls(graph, idat_pairs):
    """Load paired channels, calculate calls and return result node ids."""
    manifest = single_file(graph, "bpm")[1]["content"]
    egt_file = single_file(graph, "egt")[1]
    manifest_rows = single_file(graph, "csv")[1].get("content", [])
    egt_content = list(egt_file["content"].name2cluster_record.values())
    egt_addresses = [entry.address for entry in egt_content]
    result_ids = []

    for batch_idx, (green_id, red_id) in enumerate(idat_pairs):
        green_attrs = graph.G.nodes[green_id]
        red_attrs = graph.G.nodes[red_id]
        green_data = read_idat_data(green_id)
        red_data = read_idat_data(red_id)
        green_attrs["data"] = green_data
        red_attrs["data"] = red_data

        aligned = align_ids(
            green_data.get("illumina_ids", []),
            red_data.get("illumina_ids", []),
            egt_addresses,
            manifest,
        )
        calls = filter_strongest_signal(
            green_data, red_data, egt_content, aligned, manifest
        )
        result_id = f"result:{batch_idx}"
        graph.add_node(
            {
                "id": result_id,
                "type": "SCORE_RESULT",
                "call_count": len(calls),
                "data": calls,
            }
        )
        sample_id = _sample_node(graph, green_attrs)
        for file_id in (green_id, red_id):
            graph.add_edge(
                sample_id,
                file_id,
                attrs={
                    "rel": "has_channel",
                    "src_layer": "SAMPLE",
                    "trgt_layer": "FILE",
                },
            )
            graph.add_edge(
                file_id,
                result_id,
                attrs={
                    "rel": "resulting_calculation",
                    "src_layer": "FILE",
                    "trgt_layer": "SCORE_RESULT",
                },
            )
        graph.add_edge(
            sample_id,
            result_id,
            attrs={
                "rel": "has_result",
                "src_layer": "SAMPLE",
                "trgt_layer": "SCORE_RESULT",
            },
        )
        _materialize_calls(graph, result_id, calls, manifest_rows)
        result_ids.append(result_id)
    return result_ids


def find_call(graph, index, sample_id=None):
    candidates = [
        {"id": nid, **attrs}
        for nid, attrs in graph.G.nodes(data=True)
        if attrs.get("type") == "VARIANT_CALL" and attrs.get("index") == index
    ]
    if sample_id is None:
        return candidates[0] if len(candidates) == 1 else candidates
    sample_neighbors = set(graph.G.neighbors(sample_id))
    for call in candidates:
        if any(
            parent in sample_neighbors for parent in graph.G.neighbors(call["id"])
        ):
            return call
    return None
