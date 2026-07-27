# Delete-file_master route: remove user file_master via GBucket + RTDB history
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from user.views.gbucket import get_bucket, record_file_history, require_user_id, user_prefix


# APIView for DELETE/POST /api/user/delete-file_master/
class DeleteFileView(APIView):

    # Delete blob at authenticated user prefix path
    def post(self, request):
        # require JWT-derived billing uid
        user_id, auth_error = require_user_id(request)
        if auth_error:
            return auth_error
        # file_master name from request body
        file_name = request.data.get("name") or request.data.get("file_name", "")
        # full bucket path to delete
        dest_path = f"{user_prefix(request)}{file_name}"
        # single GBucket call
        get_bucket().delete_blob(dest_path)
        # RTDB audit trail
        record_file_history(request, action="user.delete_file", file_name=file_name)
        return Response(
            {"success": True, "user_id": user_id, "name": file_name, "detail": "delete-file_master"},
            status=status.HTTP_200_OK,
        )

    # DELETE delegates to POST so request.data can carry auth in body
    def delete(self, request):
        return self.post(request)
