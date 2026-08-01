from __future__ import annotations

import mimetypes
from pathlib import Path
from tempfile import TemporaryDirectory

import networkx as nx
from django.http import FileResponse, Http404
from django.shortcuts import render
from django.urls import reverse
from rest_framework.response import Response
from rest_framework.views import APIView

from drug_master.artifacts import artifact_path, build_artifacts, register_export
from drug_master.live_evidence import collect_live_evidence
from drug_master.precision_workflow import build_precision_drug_graph
from firegraph.graph.local_graph_utils import GUtils


DEFAULT_PROTEINS = [
    "Q15822", "P24046", "O43525", "Q9Y3Q4", "Q9P2U8", "Q96PR1",
    "B7Z3W4", "B7Z3R2", "B7Z3V7", "B2R6C6", "B7Z3Y0", "B2RCL0",
    "B4DKD3", "B4DKC0", "B4DKD1",
]


class ResearchGraph(GUtils):
    def __init__(self, file_store):
        super().__init__(
            G=nx.Graph(),
            nx_only=True,
            enable_data_store=False,
            file_store=file_store,
        )

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

        temp_store = TemporaryDirectory(prefix="cnvmaster-drug-export-")
        registered = False
        try:
            evidence = collect_live_evidence(accessions, max_depth=10)
            evidence["vep_annotations"] = variants
            graph = ResearchGraph(file_store=temp_store)
            result = build_precision_drug_graph(
                graph,
                accessions,
                **evidence,
                sex=sex,
            )
            payload = graph.payload()
            export_id = register_export(temp_store)
            registered = True

            def download_url(filename):
                return request.build_absolute_uri(reverse(
                    "drug_master:artifact",
                    kwargs={"export_id": export_id, "filename": filename},
                ))

            artifacts = build_artifacts(
                graph,
                result,
                directory=Path(temp_store.name),
                download_url=download_url,
            )
            result["nx_graph_file_path"] = artifacts["nx_graph"]["url"]
            result["order_pdf_path"] = artifacts["order_pdf"]["url"]
            result["process_sum_pdf_path"] = artifacts["process_pdf"]["url"]
            return Response({
                "result": result,
                "graph": payload,
                "export_id": export_id,
                "tempstore_route": request.build_absolute_uri(
                    reverse(
                        "drug_master:artifact",
                        kwargs={
                            "export_id": export_id,
                            "filename": "precision_drug_graph.json",
                        },
                    )
                ).rsplit("/", 1)[0] + "/",
                "artifacts": artifacts,
                "summary": {
                    "nodes": len(payload["nodes"]),
                    "edges": len(payload["edges"]),
                    "targets": len(result["target_ids"]),
                    "drugs": len(result["drug_ids"]),
                },
            })
        except Exception as exc:
            return Response({"error": str(exc)}, status=502)
        finally:
            if not registered:
                temp_store.cleanup()


class DrugArtifactDownload(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, export_id: str, filename: str):
        path = artifact_path(export_id, filename)
        if path is None:
            raise Http404("Artifact not found or expired.")
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return FileResponse(
            path.open("rb"),
            content_type=content_type,
            as_attachment=path.suffix.lower() != ".html",
            filename=path.name,
        )
