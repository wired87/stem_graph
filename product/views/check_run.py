from django.http import FileResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from product.models import StemCNVRun
from product.stemcnv_docker import StemCNVDockerError, archive_run, cancel_run, get_download_name, get_run


class DockerStatusAndDownloadView(APIView):
    def get(self, request, container_id, *args, **kwargs):
        try:
            if request.query_params.get("download") in {"1", "true", "yes"}:
                archive = archive_run(container_id)
                return FileResponse(archive, as_attachment=True, filename=get_download_name(container_id))
            payload = get_run(container_id)
        except FileNotFoundError:
            return Response({"detail": "StemCNV run not found"}, status=status.HTTP_404_NOT_FOUND)
        except StemCNVDockerError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        code = status.HTTP_202_ACCEPTED if payload["status"] in {
            "queued", "starting", "created", "running"
        } else status.HTTP_200_OK
        if payload["status"] == "failed":
            code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return Response(payload, status=code)

    def post(self, request, container_id, *args, **kwargs):
        if request.data.get("action") != "cancel":
            return Response({"detail": "Supported action: cancel"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            return Response(cancel_run(container_id))
        except StemCNVRun.DoesNotExist:
            return Response({"detail": "StemCNV run not found"}, status=status.HTTP_404_NOT_FOUND)


class LatestStemCNVRunView(APIView):
    def get(self, request, *args, **kwargs):
        latest = StemCNVRun.objects.filter(
            status__in=["queued", "starting", "created", "running"]
        ).first() or StemCNVRun.objects.first()
        if latest is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        try:
            return Response(get_run(latest.run_id))
        except (FileNotFoundError, StemCNVDockerError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
