
from django.http import FileResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView



import dotenv

from product.run_local import run_local

dotenv.load_dotenv()

"""
# Per-step timings written after each run
TIMING_PATH = os.path.abspath(
os.path.join(tmp_store.name, 'logs', 'execution_timing.json'))
os.makedirs(TIMING_PATH, exist_ok=True)

# Execution metadata uploaded to GCS session output dir
METADATA_PATH = os.path.abspath(os.path.join(tmp_store.name, 'logs', 'metadata.json'))
os.makedirs(METADATA_PATH, exist_ok=True)

# Out dir
OUTPUT_PATH = os.path.abspath(os.path.join(tmp_store.name, 'output'))
os.makedirs(OUTPUT_PATH, exist_ok=True)
"""


class RunLocalSampleView(APIView):

    def post(self, request):
        files = request.FILES.getlist("files")
        try:
            container_id=run_local(files)
            if container_id is None:
                return Response(dict(error="sample table not found"), status=status.HTTP_400_BAD_REQUEST)

            return Response(
                {"run_id": container_id},
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            print("Err1", exc)
            return Response(
                {"detail": "batch submit failed", "error": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
