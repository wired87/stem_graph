# Status-run route: inspect or cancel GCP Batch jobs for product runs
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from product.batch import BatchManager


# APIView for GET/POST /api/product/status-run/
class StatusRunView(APIView):

    # Return batch job status (by job_id, session_id label, or list for user)
    def get(self, request):
        job_id = request.query_params.get("job_id") or request.data.get("job_id")
        session_id = request.query_params.get("session_id") or request.data.get("session_id")
        user_id = request.query_params.get("user_id") or request.data.get("user_id") or request.data.get("auth")
        action = (request.query_params.get("action") or request.data.get("action") or "status").lower()

        try:
            manager = BatchManager()
            if action == "cancel" and job_id:
                result = manager.cancel_job(job_id)
                return Response(result, status=status.HTTP_200_OK)

            if job_id:
                return Response(manager.get_job(job_id), status=status.HTTP_200_OK)

            jobs = manager.list_jobs(user_id=user_id, limit=50)
            if session_id:
                sid = session_id.lower().replace("_", "-")
                jobs = [j for j in jobs if j.get("labels", {}).get("sessionId") == sid or j.get("labels", {}).get("session_id") == sid]
            if not jobs:
                return Response(
                    {"detail": "no matching batch jobs", "session_id": session_id, "user_id": user_id},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if session_id and len(jobs) == 1:
                return Response(jobs[0], status=status.HTTP_200_OK)
            return Response({"jobs": jobs}, status=status.HTTP_200_OK)

        except Exception as exc:
            return Response(
                {"detail": "batch status failed", "error": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

    # POST supports same lookups when clients send body instead of query params
    def post(self, request):
        return self.get(request)
