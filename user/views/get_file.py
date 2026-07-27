# Get-file_master route: fetch authenticated user file_master via GBucket + RTDB history
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from user.views.gbucket import get_bucket, record_file_history, require_user_id, user_prefix


# APIView for GET/POST /api/user/get-file_master/
class GetFileView(APIView):

    # Download blob text for JWT-authenticated user file_master name
    def post(self, request):
        # require JWT-derived billing uid
        user_id, auth_error = require_user_id(request)
        if auth_error:
            return auth_error
        # file_master name from request body
        file_name = request.data.get("name") or request.data.get("file_name", "")
        # full bucket path under user prefix
        bucket_path = f"{user_prefix(request)}{file_name}"
        # single GBucket call
        content = get_bucket().download_blob(bucket_path)
        # RTDB audit trail
        record_file_history(request, action="user.get_file", file_name=file_name)
        return Response(
            {"success": True, "user_id": user_id, "name": file_name, "content": content},
            status=status.HTTP_200_OK,
        )

    # GET delegates to POST so query/body can carry file_master name
    def get(self, request):
        return self.post(request)
