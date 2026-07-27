# Set-file_master route: create user file_master via GBucket + RTDB history
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from fb_core.storage import ensure_user_bucket_folder
from user.views.gbucket import get_bucket, record_file_history, require_user_id, user_prefix


# APIView for POST /api/user/set-file_master/
class SetFileView(APIView):

    # Upload new file_master content to authenticated user prefix path
    def post(self, request):
        # require JWT-derived billing uid
        user_id, auth_error = require_user_id(request)
        if auth_error:
            return auth_error
        # ensure user folder exists (registration-style fb_core helper)
        ensure_user_bucket_folder(user_id=user_id)
        # file_master name and content from request body
        file_name = request.data.get("name") or request.data.get("file_name", "")
        content = request.data.get("content", "")
        # full bucket destination path
        dest_path = f"{user_prefix(request)}{file_name}"
        # single GBucket call
        get_bucket().upload_from_str(dest_path, content)
        # RTDB audit trail
        record_file_history(request, action="user.set_file", file_name=file_name)
        return Response(
            {"success": True, "user_id": user_id, "name": file_name, "detail": "set-file_master"},
            status=status.HTTP_201_CREATED,
        )
