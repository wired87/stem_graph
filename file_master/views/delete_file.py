# Delete-file_master route: remove file_master via GBucket.delete_blob
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from file_master.views.gbucket import get_bucket, user_id_from_request, user_prefix


# APIView for DELETE/POST /api/file_master/delete-file_master/
class DeleteFileView(APIView):

    # Delete blob at user prefix path
    def post(self, request):
        # file_master name from request body
        file_name = request.data.get('name') or request.data.get('file_name', '')
        # full bucket path to delete
        dest_path = f"{user_prefix(request)}{file_name}"
        # single GBucket call
        get_bucket().delete_blob(dest_path)
        return Response({'user_id': user_id_from_request(request), 'name': file_name, 'detail': 'delete-file_master'}, status=status.HTTP_200_OK)

    # DELETE delegates to POST so request.data can carry auth in body
    def delete(self, request):
        return self.post(request)
