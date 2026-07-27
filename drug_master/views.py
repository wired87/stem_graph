from __future__ import annotations

import networkx as nx
from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.views import APIView

from drug_master.live_evidence import collect_live_evidence
from drug_master.precision_workflow import build_precision_drug_graph


DEFAULT_PROTEINS = [
    "Q15822", "P24046", "O43525", "Q9Y3Q4", "Q9P2U8", "Q96PR1",
    "B7Z3W4", "B7Z3R2", "B7Z3V7", "B2R6C6", "B7Z3Y0", "B2RCL0",
    "B4DKD3", "B4DKC0", "B4DKD1",
]


class ResearchGraph:
    def __init__(self):
        self.G = nx.Graph()

    def add_node(self, attrs):
        node_id = attrs["id"]
        self.G.add_node(
            node_id,
            **{key: value for key, value in attrs.items() if key != "id"},
        )

    def add_edge(self, source, target, attrs):
        self.G.add_edge(source, target, **attrs)

    def payload(self) -> dict:
        return {
            "nodes": [
                {"id": node_id, **attrs}
                for node_id, attrs in self.G.nodes(data=True)
            ],
            "edges": [
                {"source": source, "target": target, **attrs}
                for source, target, attrs in self.G.edges(data=True)
            ],
        }


def drug_workspace(request):
    return render(
        request,
        "drug_master/workspace.html",
        {
            "default_proteins": "\n".join(DEFAULT_PROTEINS),
            "theme": "drug",
        },
    )


class PrecisionDrugWorkflow(APIView):
    def post(self, request):
        accessions = request.data.get("accessions") or DEFAULT_PROTEINS
        if isinstance(accessions, str):
            accessions = accessions.replace(",", " ").split()
        accessions = list(dict.fromkeys(
            str(value).strip().upper() for value in accessions if str(value).strip()
        ))
        if not accessions:
            return Response({"error": "At least one UniProt accession is required."}, status=400)
        if len(accessions) > 50:
            return Response({"error": "A maximum of 50 accessions is supported."}, status=400)

        variants = request.data.get("vep_annotations") or []
        if not isinstance(variants, list):
            return Response({"error": "VEP annotations must be a JSON list."}, status=400)
        sex = str(request.data.get("sex") or "").strip().lower() or None

        try:
            evidence = collect_live_evidence(accessions, max_depth=10)
            evidence["vep_annotations"] = variants
            graph = ResearchGraph()
            result = build_precision_drug_graph(
                graph,
                accessions,
                **evidence,
                sex=sex,
            )
            payload = graph.payload()
            return Response({
                "result": result,
                "graph": payload,
                "summary": {
                    "nodes": len(payload["nodes"]),
                    "edges": len(payload["edges"]),
                    "targets": len(result["target_ids"]),
                    "drugs": len(result["drug_ids"]),
                },
            })
        except Exception as exc:
            return Response({"error": str(exc)}, status=502)
