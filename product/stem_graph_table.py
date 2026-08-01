"""Tabular response view for StemGraph batch nodes.

StemGraph keeps several workflow outputs as indexed ``data`` arrays on graph
nodes.  The index inside each array is the table data index (``tdx``); rows
with the same ``tdx`` can be compared across batches, while physical graph
edges explain how the batch nodes are connected.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping


CASE_LEGENDS = {
    "harmful_variation": {
        "0": "explicit disease-associated pathogenic evidence",
        "None": "not established as disease-associated pathogenic evidence",
    },
    "variant_dir": {
        "0": "INCREASE",
        "1": "DECREASE",
        "None": "unknown or conflicting directionality",
    },
    "goterm_gene_alignment": {
        "0": "gene has at least one GO term aligned to a requested function",
        "None": "no aligned GO term, no usable label, or below threshold",
    },
}


def _jsonish(value):
    if isinstance(value, Mapping):
        return {str(key): _jsonish(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonish(item) for item in value]
    return value


def _item_label(value):
    if not isinstance(value, Mapping):
        return None
    for key in (
        "id",
        "call_id",
        "name",
        "variantId",
        "drugId",
        "gene_id",
        "protein_id",
        "accession",
    ):
        if value.get(key) is not None:
            return str(value[key])
    return None


def _value_key(value):
    return "None" if value is None else str(value)


def _value_label(node_id, attrs, value):
    coding = attrs.get("coding")
    key = _value_key(value)
    if isinstance(coding, Mapping):
        for raw_label, raw_code in coding.items():
            if _value_key(raw_code) == key:
                return str(raw_label)
    return CASE_LEGENDS.get(node_id, {}).get(key)


def _neighbor_edges(graph, node_id):
    edges = []
    for neighbor_id in graph.neighbors(node_id):
        attrs = graph.get_edge_data(node_id, neighbor_id) or {}
        edges.append(
            {
                "source": str(node_id),
                "target": str(neighbor_id),
                "rel": attrs.get("rel"),
                "source_layer": attrs.get("src_layer"),
                "target_layer": attrs.get("trgt_layer"),
                "index": attrs.get("index"),
                "attrs": _jsonish(attrs),
            }
        )
    return edges


def _node_legend(node_id, attrs):
    legend = {}
    if attrs.get("semantics"):
        legend["semantics"] = attrs["semantics"]
    if isinstance(attrs.get("coding"), Mapping):
        legend["coding"] = _jsonish(attrs["coding"])
    if attrs.get("method"):
        legend["method"] = attrs["method"]
    if attrs.get("warning"):
        legend["warning"] = attrs["warning"]
    if node_id in CASE_LEGENDS:
        legend["values"] = CASE_LEGENDS[node_id]
    return legend


def build_stem_graph_table(graph):
    """Return a tabular, legend-bearing representation of StemGraph batches."""
    rows = []
    tdx_groups = defaultdict(dict)
    batch_nodes = []
    legend_nodes = {}

    for node_id, attrs in graph.nodes(data=True):
        data = attrs.get("data")
        if not isinstance(data, list):
            node_legend = _node_legend(node_id, attrs)
            if node_legend:
                legend_nodes[str(node_id)] = node_legend
            continue

        node_id = str(node_id)
        node_legend = _node_legend(node_id, attrs)
        if node_legend:
            legend_nodes[node_id] = node_legend
        batch_nodes.append(
            {
                "batch_id": node_id,
                "batch_type": attrs.get("type"),
                "rows": len(data),
                "physical_edges": _neighbor_edges(graph, node_id),
            }
        )

        for tdx, value in enumerate(data):
            row = {
                "tdx": tdx,
                "batch_id": node_id,
                "batch_type": attrs.get("type"),
                "item_id": _item_label(value),
                "value": _jsonish(value),
                "value_label": _value_label(node_id, attrs, value),
                "physical_edges": _neighbor_edges(graph, node_id),
            }
            rows.append(row)
            tdx_groups[tdx][node_id] = row["value"]

    edge_rows = [
        {
            "source": str(source),
            "target": str(target),
            "rel": attrs.get("rel"),
            "source_layer": attrs.get("src_layer"),
            "target_layer": attrs.get("trgt_layer"),
            "index": attrs.get("index"),
            "attrs": _jsonish(attrs),
        }
        for source, target, attrs in graph.edges(data=True)
    ]

    return {
        "columns": [
            "tdx",
            "batch_id",
            "batch_type",
            "item_id",
            "value",
            "value_label",
            "physical_edges",
        ],
        "rows": rows,
        "tdx_groups": [
            {"tdx": tdx, "items": items}
            for tdx, items in sorted(tdx_groups.items())
        ],
        "batch_nodes": batch_nodes,
        "physical_edges": edge_rows,
        "legend": {
            "tdx": (
                "Table data index inside one batch. Items with equal tdx are "
                "index-related across batch nodes."
            ),
            "physical_edges": (
                "NetworkX graph edges connecting files, samples, results, "
                "variant calls, annotations, genes, proteins, and evidence nodes."
            ),
            "node_value_meanings": legend_nodes,
        },
    }
