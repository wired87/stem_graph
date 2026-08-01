from pathlib import Path
from tempfile import TemporaryDirectory

from django.urls import reverse
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from cnvmaster.middleware import HybridResponseMixin
from drug_master.artifacts import register_export
from drug_master.views import ResearchGraph
from .serializers import PrecisionDrugSerializer
from .workflows import run_precision_drug_workflow


class PrecisionDrugComponentView(HybridResponseMixin, APIView):
    parser_classes = [MultiPartParser, FormParser]
    renderer_classes = [JSONRenderer, TemplateHTMLRenderer]
    template_name = "drug_master/components/precision_drug/precision_drug.html"

    def post(self, request):
        serializer = PrecisionDrugSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return self.validation_error_response(request, self.template_name, serializer.errors)
        temp_store = TemporaryDirectory(prefix="cnvmaster-drug-export-")
        registered = False
        try:
            graph = ResearchGraph(file_store=temp_store)
            export_id = register_export(temp_store)
            registered = True

            def download_url(filename):
                return request.build_absolute_uri(reverse(
                    "drug_master:artifact", kwargs={"export_id": export_id, "filename": filename}
                ))

            result, payload, artifacts = run_precision_drug_workflow(
                graph=graph, directory=Path(temp_store.name), download_url=download_url,
                **serializer.validated_data,
            )
            return Response({
                "result": result, "graph": payload, "export_id": export_id,
                "tempstore_route": download_url("precision_drug_graph.json").rsplit("/", 1)[0] + "/",
                "artifacts": artifacts,
                "summary": {"nodes": len(payload["nodes"]), "edges": len(payload["edges"]),
                            "targets": len(result["target_ids"]), "drugs": len(result["drug_ids"])},
            })
        except Exception as exc:
            return self.component_response(
                request, self.template_name, {"error": str(exc), "message": str(exc)}, status_code=502
            )
        finally:
            if not registered:
                temp_store.cleanup()
