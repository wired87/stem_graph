from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from cnvmaster.middleware import HybridResponseMixin
from .serializers import StemGraphSerializer
from .workflows import run_stem_graph


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
        graph = None
        try:
            graph, payload = run_stem_graph(**serializer.validated_data)
            return Response(payload)
        except ValueError as exc:
            return self.component_response(
                request, self.template_name, {"detail": str(exc), "message": str(exc)}, status_code=400
            )
        except Exception as exc:
            return self.component_response(request, self.template_name, {
                "detail": "StemCNV graph processing failed", "error": str(exc), "message": str(exc)
            }, status_code=502)
        finally:
            if graph is not None:
                graph.close()
