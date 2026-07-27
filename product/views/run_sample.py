# Run-sample route: submit StemCNV session as a GCP Batch job
import os
import uuid

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from product.batch import BatchHardware, BatchManager


# APIView for POST /api/product/run-sample/
class RunSampleView(APIView):

    # Submit executable run via GCP Batch (EXEC_DOCKER_PATH + request hardware)
    def post(self, request):
        user_id = request.data.get("user_id") or request.data.get("auth", "")
        session_id = request.data.get("session_id") or uuid.uuid4().hex
        job_id = request.data.get("job_id")
        env_overrides = request.data.get("env") or {}
        hardware = BatchHardware.from_request(request.data)

        if not user_id:
            return Response(
                {"detail": "user_id or auth is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Docker image endpoint from EXEC_DOCKER_PATH (required for batch runs)
        image_uri = os.getenv("EXEC_DOCKER_PATH", "").strip()
        if not image_uri:
            return Response(
                {"detail": "EXEC_DOCKER_PATH must be set"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Merge explicit env with hardware-derived StemCNV limits
        merged_env = {}
        if isinstance(env_overrides, dict):
            merged_env.update({k: str(v) for k, v in env_overrides.items()})
        merged_env.update(hardware.env_overrides())

        try:
            manager = BatchManager()
            job = manager.submit_session_job(
                user_id=user_id,
                session_id=session_id,
                job_id=job_id,
                env_overrides=merged_env,
                hardware=hardware,
                image_uri=image_uri,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response(
                {"detail": "batch submit failed", "error": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "job_id": job["job_id"],
                "user_id": job["user_id"],
                "session_id": job["session_id"],
                "state": job["state"],
                "name": job["name"],
                "image_uri": job["image_uri"],
                "hardware": job["hardware"],
            },
            status=status.HTTP_202_ACCEPTED,
        )
