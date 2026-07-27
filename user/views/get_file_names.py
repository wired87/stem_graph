# Get-file_master-names route: list JWT-authenticated user files via GBucket
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from user.views.gbucket import get_bucket, record_file_history, require_user_id, user_prefix


# APIView for GET/POST /api/user/get-file_master-names/
class GetFileNamesView(APIView):

    # List object paths under authenticated user prefix in bucket
    def post(self, request):
        # require JWT-derived billing uid
        user_id, auth_error = require_user_id(request)
        if auth_error:
            return auth_error
        # user-scoped prefix for listing
        prefix = user_prefix(request)
        # single GBucket call
        bucket = get_bucket()
        file_names = bucket.extract_gcs_train_tree(bucket.bucket_name, prefix=prefix)
        # RTDB audit trail
        record_file_history(
            request,
            action="user.get_file_names",
            file_name="*",
            details={"count": len(file_names)},
        )
        return Response(
            {"success": True, "user_id": user_id, "file_names": file_names},
            status=status.HTTP_200_OK,
        )

    # GET delegates to POST for consistent auth handling
    def get(self, request):
        return self.post(request)
