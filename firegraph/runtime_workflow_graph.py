"""
Runtime knowledge-graph adapter for the biological workflows.

This keeps peptide and amino-acid runs on a small, typed graph surface while
reusing the bundled firegraph directory as the storage/export home.
"""
from __future__ import annotations

import importlib.util
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import networkx as nx

_GRAPH_UTILS_PATH = Path(__file__).resolve().parent / "graph" / "local_graph_utils.py"


def _slug(text: str) -> str:
    return re.sub(r"[^\w\-]+", "_", text).strip("_")[:80] or "item"


def _serialize_value(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, set):
            return sorted(_serialize_value(item) for item in value)
        if isinstance(value, dict):
            return {str(key): _serialize_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [_serialize_value(item) for item in value]
        return str(value)


class _MinimalGraphUtils:
    """Fallback matching the small GUtils surface used by the workflows."""

    def __init__(self, G: nx.MultiGraph | None = None, nx_only: bool = True, **_: Any):
        self.G = G if G is not None else nx.MultiGraph()
        self.nx_only = nx_only

    def add_node(self, attrs: dict[str, Any], flatten: bool = False) -> bool:
        del flatten
        node_id = attrs["id"]
        node_attrs = {key: _serialize_value(value) for key, value in attrs.items() if key != "id"}
        node_attrs["type"] = str(node_attrs.get("type", "NODE")).upper()
        self.G.add_node(node_id, **node_attrs)
        return True

    def add_edge(
        self,
        src: str | None = None,
        trgt: str | None = None,
        attrs: dict[str, Any] | None = None,
        **_: Any,
    ) -> None:
        attrs = attrs or {}
        src = src or attrs.get("src")
        trgt = trgt or attrs.get("trgt")
        if src is None or trgt is None:
            raise ValueError("Edges require src and trgt identifiers.")
        rel = str(attrs.get("rel", "related_to")).lower().replace(" ", "_")
        edge_attrs = {
            key: _serialize_value(value)
            for key, value in attrs.items()
            if key not in {"src", "trgt"}
        }
        edge_attrs["rel"] = rel
        edge_attrs["src_layer"] = str(edge_attrs.get("src_layer", "NODE")).upper()
        edge_attrs["trgt_layer"] = str(edge_attrs.get("trgt_layer", "NODE")).upper()
        edge_attrs["eid"] = edge_attrs.get("eid") or f"{src}_{rel}_{trgt}"
        edge_attrs["type"] = f"{edge_attrs['src_layer']}_{rel}_{edge_attrs['trgt_layer']}"
        self.G.add_edge(src, trgt, **edge_attrs)

    def save_graph(self, dest_file: str | Path) -> None:
        data = nx.node_link_data(self.G)
        Path(dest_file).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _load_firegraph_gutils() -> type[_MinimalGraphUtils]:
    try:
        spec = importlib.util.spec_from_file_location("firegraph_local_graph_utils", _GRAPH_UTILS_PATH)
        if spec is None or spec.loader is None:
            return _MinimalGraphUtils
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        gutils_cls = getattr(module, "GUtils", None)
        if gutils_cls is None:
            return _MinimalGraphUtils
        return gutils_cls
    except Exception:
        return _MinimalGraphUtils


@dataclass
class GraphExport:
    graph_path: str
    graph_summary_path: str
    graph_node_count: int
    graph_edge_count: int
    graph_summary: dict[str, Any]


class WorkflowRuntimeGraph:
    """Typed firegraph-friendly runtime graph for one workflow execution."""

    def __init__(self, workflow_type: str, goal_text: str):
        self.workflow_type = workflow_type.lower()
        self.run_id = f"{self.workflow_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
        self.goal_text = goal_text
        self.G = nx.MultiGraph()
        gutils_cls = _load_firegraph_gutils()
        self.gutils = gutils_cls(G=self.G, nx_only=True)
        self.case_node_id = self._node_id("case_run", "root")
        self.goal_node_id: str | None = None
        self._add_node(
            self.case_node_id,
            "CASE_RUN",
            workflow_type=self.workflow_type,
            run_id=self.run_id,
            created_at=datetime.now().isoformat(),
        )

    def _node_id(self, node_type: str, suffix: str) -> str:
        return f"{self.run_id}:{node_type}:{_slug(suffix)}"

    def _add_node(self, node_id: str, node_type: str, **attrs: Any) -> str:
        payload = {
            "id": node_id,
            "type": node_type,
            **{key: _serialize_value(value) for key, value in attrs.items()},
        }
        self.gutils.add_node(payload)
        return node_id

    def _add_edge(
        self,
        src: str,
        trgt: str,
        rel: str,
        src_type: str,
        trgt_type: str,
        **attrs: Any,
    ) -> None:
        payload = {
            "src": src,
            "trgt": trgt,
            "rel": rel,
            "src_layer": src_type,
            "trgt_layer": trgt_type,
            **{key: _serialize_value(value) for key, value in attrs.items()},
        }
        self.gutils.add_edge(src=src, trgt=trgt, attrs=payload)

    def add_goal(self, goal_text: str, **attrs: Any) -> str:
        goal_node_id = self._node_id("goal", goal_text[:60])
        self._add_node(goal_node_id, "GOAL", text=goal_text, **attrs)
        self._add_edge(self.case_node_id, goal_node_id, "has_goal", "CASE_RUN", "GOAL")
        self.goal_node_id = goal_node_id
        return goal_node_id

    def add_field(self, field_id: str, label: str, group: str) -> str:
        node_id = self._node_id("uniprot_field", field_id)
        self._add_node(node_id, "UNIPROT_FIELD", field_id=field_id, label=label, group=group)
        self._add_edge(self.case_node_id, node_id, "selects_field", "CASE_RUN", "UNIPROT_FIELD")
        if self.goal_node_id is not None:
            self._add_edge(self.goal_node_id, node_id, "focuses_on", "GOAL", "UNIPROT_FIELD")
        return node_id

    def add_protein_entry(
        self,
        accession: str,
        name: str,
        gene_names: list[str],
        category: str,
        sequence: str,
        functional_specs: dict[str, Any],
    ) -> str:
        node_id = self._node_id("protein_entry", accession)
        self._add_node(
            node_id,
            "PROTEIN_ENTRY",
            accession=accession,
            name=name,
            gene_names=gene_names,
            category=category,
            sequence_length=len(sequence),
            sequence_preview=sequence[:80],
            functional_specs=functional_specs,
        )
        self._add_edge(self.case_node_id, node_id, "retrieves_candidate", "CASE_RUN", "PROTEIN_ENTRY")
        if self.goal_node_id is not None:
            self._add_edge(self.goal_node_id, node_id, "supports_goal", "GOAL", "PROTEIN_ENTRY")
        return node_id

    def add_feature_span(
        self,
        protein_node_id: str,
        accession: str,
        label: str,
        start: int,
        end: int,
        sequence: str,
    ) -> str:
        node_id = self._node_id("feature_span", f"{accession}_{label}_{start}_{end}")
        self._add_node(
            node_id,
            "FEATURE_SPAN",
            accession=accession,
            label=label,
            start=start,
            end=end,
            length=len(sequence),
            sequence=sequence,
        )
        self._add_edge(protein_node_id, node_id, "has_feature", "PROTEIN_ENTRY", "FEATURE_SPAN")
        return node_id

    def add_score(
        self,
        protein_node_id: str,
        accession: str,
        score_value: float,
        score_kind: str,
    ) -> str:
        node_id = self._node_id(score_kind.lower(), accession)
        self._add_node(
            node_id,
            score_kind.upper(),
            accession=accession,
            score=float(score_value),
        )
        self._add_edge(protein_node_id, node_id, "scored_as", "PROTEIN_ENTRY", score_kind.upper())
        return node_id

    def add_text_payload(self, node_type: str, label: str, **attrs: Any) -> str:
        node_id = self._node_id(node_type.lower(), label)
        self._add_node(node_id, node_type.upper(), **attrs)
        return node_id

    def connect(self, src: str, trgt: str, rel: str, src_type: str, trgt_type: str, **attrs: Any) -> None:
        self._add_edge(src, trgt, rel, src_type, trgt_type, **attrs)

    def add_artifact(self, artifact_type: str, path: str | Path, **attrs: Any) -> str:
        artifact_path = str(path)
        node_id = self._node_id("artifact", Path(artifact_path).name)
        self._add_node(node_id, "ARTIFACT", artifact_type=artifact_type, path=artifact_path, **attrs)
        self._add_edge(self.case_node_id, node_id, "writes_artifact", "CASE_RUN", "ARTIFACT")
        return node_id

    def export(self, base_artifact_path: str | Path, goal_summary: str) -> GraphExport:
        artifact_path = Path(base_artifact_path)
        graph_path = artifact_path.with_suffix(".graph.json")
        graph_summary_path = artifact_path.with_suffix(".graph.summary.json")

        self.gutils.save_graph(graph_path)

        node_counts = Counter(
            attrs.get("type", "UNKNOWN")
            for _, attrs in self.G.nodes(data=True)
        )
        edge_counts = Counter(
            attrs.get("rel", "related_to")
            for _, _, attrs in self.G.edges(data=True)
        )
        summary = {
            "run_id": self.run_id,
            "workflow_type": self.workflow_type,
            "goal_summary": goal_summary,
            "node_count": self.G.number_of_nodes(),
            "edge_count": self.G.number_of_edges(),
            "node_types": dict(sorted(node_counts.items())),
            "edge_relations": dict(sorted(edge_counts.items())),
        }
        graph_summary_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return GraphExport(
            graph_path=str(graph_path),
            graph_summary_path=str(graph_summary_path),
            graph_node_count=self.G.number_of_nodes(),
            graph_edge_count=self.G.number_of_edges(),
            graph_summary=summary,
        )
