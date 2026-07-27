# Update-file_master route: overwrite file_master via GBucket.upload_from_str
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from file_master.views.gbucket import get_bucket, user_id_from_request, user_prefix


# APIView for PUT/POST /api/file_master/update-file_master/
class UpdateFileView(APIView):

    # Overwrite existing file_master content at user prefix path
    def post(self, request):
        # file_master name and new content from request body
        file_name = request.data.get('name') or request.data.get('file_name', '')
        content = request.data.get('content', '')
        # full bucket destination path
        dest_path = f"{user_prefix(request)}{file_name}"
        # single GBucket call (overwrite)
        get_bucket().upload_from_str(dest_path, content)
        return Response({'user_id': user_id_from_request(request), 'name': file_name, 'detail': 'update-file_master'}, status=status.HTTP_200_OK)

    # PUT delegates to POST so request.data can carry auth in body
    def put(self, request):
        return self.post(request)
