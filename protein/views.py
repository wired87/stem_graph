import asyncio
import mimetypes
from pathlib import Path
from tempfile import TemporaryDirectory

from django.http import FileResponse, Http404
from django.shortcuts import render
from django.urls import reverse
from rest_framework.response import Response
from rest_framework.views import APIView

from firegraph.graph.local_graph_utils import GUtils
from protein.artifacts import artifact_path, create_aum_pdf, register_export
from protein.workflow import predict_proteins


def filter_protein_entries(g: GUtils):
    outsrc_keys = {
        "id",
        "primaryAccession",
        "xrefs",
        "uniProtKBCrossReferences",
        "secondaryAccessions",
        "uniProtkbId",
        "entryAudit",
        "proteinExistence",
        "annotationScore",
        "proteinDescription",  # Fixed trailing space here
        "organism",
        "features",
        "references",
        "embed_key",
        "extraAttributes",
    }

    proteins = g.nodes_by_type("PROTEIN")
    filtered = []

    for nid, attrs in proteins:
        # 1. Keep only the keys that are in your allowed list
        new_attrs={}
        protein_desc = attrs.get("proteinDescription", {}) or {}
        rec_name = protein_desc.get("recommendedName", {}) or {}
        full_name = rec_name.get("fullName", {}) or {}
        new_attrs["description"] = full_name.get("value", "unknown")
        genes = attrs.get("genes", []) or []
        first_gene = genes[0] if isinstance(genes, list) and genes else {}
        new_attrs["gene"] = (
            (first_gene.get("geneName", {}) or {}).get("value")
            if isinstance(first_gene, dict)
            else None
        ) or "unknown"
        comments = attrs.get("comments", []) or []
        first_comment = comments[0] if isinstance(comments, list) and comments else {}
        texts = first_comment.get("texts", []) or []
        first_text = texts[0] if isinstance(texts, list) and texts else {}
        new_attrs["text"] = first_text.get("value", "unknown")
        new_attrs["id"] = nid
        new_attrs["score"] = attrs.get("protein_score", 0)
        new_attrs["evidence"] = attrs.get("evidence", {})
        filtered.append(new_attrs)
    return sorted(filtered, key=lambda item: item["score"], reverse=True)


def protein_workspace(request):
    """Interactive Django template adapted from ProteinMasterGui."""
    return render(request, "protein/workspace.html", {"theme": "protein"})

class ProteinPredictor(APIView):

    def post(self, request):
        # todo: get proteins for entire brain and classified sub regions -> use tissue expression and uberon ids to
        # filter just porteins include genes with exp lvl > 0
        # todo perform search to identify
        print("create protein graph...")
        try:
            tissue = request.data.get("tissue")
            protein_type = request.data.get("protein_type")
            functional_annotation = request.data.get(
                "functional_annotation"
            )
            print("tissue", tissue)
            print("protein_type", protein_type)
            print("functional_annotation", functional_annotation)

            g = asyncio.run(
                predict_proteins(
                    functional_annotation=functional_annotation,
                    tissue=tissue,
                    protein_type=protein_type
                )
            )

            print("protein graph created... done")

            proteins = filter_protein_entries(g)

            response_object = dict(proteins=proteins)
            temp_store = TemporaryDirectory(prefix="cnvmaster-protein-export-")
            pdf_path = Path(temp_store.name) / "aum.pdf"
            fingerprint = create_aum_pdf(pdf_path, response_object)
            export_id = register_export(temp_store)
            pdf_url = request.build_absolute_uri(reverse(
                "protein_predictor:aum_pdf",
                kwargs={"export_id": export_id},
            ))
            g.G = None
            print("return porteins:", len(proteins))
            return Response({
                **response_object,
                "response_object": response_object,
                "aum_pdf": {
                    "filename": "aum.pdf",
                    "url": pdf_url,
                    "fingerprint": fingerprint,
                    "algorithm": "SHA-256",
                    "namespace": "botworld.cloud",
                },
            })
        except Exception as e:
            print("Error:", e)
            return Response(dict(error=str(e)))


class ProteinAumDownload(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, export_id: str):
        path = artifact_path(export_id)
        if path is None:
            raise Http404("AUM artifact not found or expired.")
        return FileResponse(
            path.open("rb"),
            content_type=mimetypes.guess_type(path.name)[0] or "application/pdf",
            as_attachment=True,
            filename=path.name,
        )
