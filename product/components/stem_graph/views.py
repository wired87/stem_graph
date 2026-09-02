from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from cnvmaster.middleware import HybridResponseMixin
from .serializers import StemGraphSerializer
from product.stemcnv_docker import ActiveStemCNVRunError, StemCNVDockerError, start_run


class StemGraphView(HybridResponseMixin, APIView):
    parser_classes = [MultiPartParser, FormParser]
    renderer_classes = [JSONRenderer, TemplateHTMLRenderer]
    template_name = "product/components/stem_graph/stem_graph.html"

    def post(self, request):
        data = request.data.copy()
        data.setlist("files", request.FILES.getlist("files"))
        serializer = StemGraphSerializer(data=data, context={"request": request})
        if not serializer.is_valid():
            return self.validation_error_response(request, self.template_name, serializer.errors)
        try:
            values = serializer.validated_data
            return Response(start_run(
                values.get("files", []), cores=values["cores"], output_name=values["output_name"]
            ), status=202)
        except ValueError as exc:
            return self.component_response(
                request, self.template_name, {"detail": str(exc), "message": str(exc)}, status_code=400
            )
        except ActiveStemCNVRunError as exc:
            return self.component_response(request, self.template_name, {
                "detail": str(exc), "message": str(exc)
            }, status_code=409)
        except StemCNVDockerError as exc:
            return self.component_response(request, self.template_name, {
                "detail": "StemCNV Docker execution failed", "error": str(exc), "message": str(exc)
            }, status_code=503)
