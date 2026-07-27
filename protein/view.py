import asyncio

from rest_framework.response import Response
from rest_framework.views import APIView

from firegraph.graph.local_graph_utils import GUtils
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
        new_attrs["gene"] = attrs["genes"][0]["geneName"]["value"]
        comments = attrs.get("comments", []) or []
        first_comment = comments[0] if isinstance(comments, list) and comments else {}
        texts = first_comment.get("texts", []) or []
        first_text = texts[0] if isinstance(texts, list) and texts else {}
        new_attrs["text"] = first_text.get("value", "unknown")
        new_attrs["id"] = nid
        filtered.append(new_attrs)
    return filtered

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

            g.G = None
            print("return porteins:", len(proteins))
            return Response(
                dict(proteins=proteins)
            )
        except Exception as e:
            print("Error:", e)
            return Response(dict(error=str(e)))
