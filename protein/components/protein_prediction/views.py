from pathlib import Path
from tempfile import TemporaryDirectory

from django.urls import reverse
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from cnvmaster.middleware import HybridResponseMixin
from protein.artifacts import create_aum_pdf, register_export
from .serializers import ProteinPredictionSerializer
from .workflows import run_protein_prediction


class ProteinPredictionView(HybridResponseMixin, APIView):
    parser_classes = [MultiPartParser, FormParser]
    renderer_classes = [JSONRenderer, TemplateHTMLRenderer]
    template_name = "protein/components/protein_prediction/protein_prediction.html"

    def post(self, request):
        serializer = ProteinPredictionSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return self.validation_error_response(request, self.template_name, serializer.errors)
        try:
            graph, response_object = run_protein_prediction(**serializer.validated_data)
            temp_store = TemporaryDirectory(prefix="cnvmaster-protein-export-")
            pdf_path = Path(temp_store.name) / "aum.pdf"
            fingerprint = create_aum_pdf(pdf_path, response_object)
            export_id = register_export(temp_store)
            pdf_url = request.build_absolute_uri(reverse(
                "protein_predictor:aum_pdf", kwargs={"export_id": export_id}
            ))
            graph.G = None
            return Response({
                **response_object, "response_object": response_object,
                "aum_pdf": {"filename": "aum.pdf", "url": pdf_url,
                            "fingerprint": fingerprint, "algorithm": "SHA-256",
                            "namespace": "botworld.cloud"},
            })
        except Exception as exc:
            return self.component_response(
                request, self.template_name, {"error": str(exc), "message": str(exc)}, status_code=502
            )
