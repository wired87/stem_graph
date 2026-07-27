# Get-file_master route: fetch file_master content via GBucket.download_blob
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from file_master.views.gbucket import get_bucket, user_id_from_request, user_prefix


# APIView for GET/POST /api/file_master/get-file_master/
class GetFileView(APIView):

    # Download blob text for user file_master name
    def post(self, request):
        # file_master name from request body
        file_name = request.data.get('name') or request.data.get('file_name', '')
        # full bucket path under user prefix
        bucket_path = f"{user_prefix(request)}{file_name}"
        # single GBucket call
        content = get_bucket().download_blob(bucket_path)
        return Response({'user_id': user_id_from_request(request), 'name': file_name, 'content': content}, status=status.HTTP_200_OK)

    # GET delegates to POST so request.data can carry auth in body
    def get(self, request):
        return self.post(request)
