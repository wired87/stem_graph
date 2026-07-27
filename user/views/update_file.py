# Update-file_master route: overwrite user file_master via GBucket + RTDB history
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from user.views.gbucket import get_bucket, record_file_history, require_user_id, user_prefix


# APIView for PUT/POST /api/user/update-file_master/
class UpdateFileView(APIView):

    # Overwrite existing file_master content at authenticated user prefix path
    def post(self, request):
        # require JWT-derived billing uid
        user_id, auth_error = require_user_id(request)
        if auth_error:
            return auth_error
        # file_master name and new content from request body
        file_name = request.data.get("name") or request.data.get("file_name", "")
        content = request.data.get("content", "")
        # full bucket destination path
        dest_path = f"{user_prefix(request)}{file_name}"
        # single GBucket call (overwrite)
        get_bucket().upload_from_str(dest_path, content)
        # RTDB audit trail
        record_file_history(request, action="user.update_file", file_name=file_name)
        return Response(
            {"success": True, "user_id": user_id, "name": file_name, "detail": "update-file_master"},
            status=status.HTTP_200_OK,
        )

    # PUT delegates to POST so request.data can carry auth + payload
    def put(self, request):
        return self.post(request)
