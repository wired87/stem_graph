# Get-file_master-names route: list file_master names via GBucket.extract_gcs_train_tree
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from file_master.views.gbucket import get_bucket, user_id_from_request, user_prefix


# APIView for GET/POST /api/file_master/get-file_master-names/
class GetFileNamesView(APIView):

    # List object paths under user prefix in bucket
    def post(self, request):
        # user-scoped prefix for listing
        prefix = user_prefix(request)
        # single GBucket call
        bucket = get_bucket()
        file_names = bucket.extract_gcs_train_tree(bucket.bucket_name, prefix=prefix)
        return Response({'user_id': user_id_from_request(request), 'file_names': file_names}, status=status.HTTP_200_OK)

    # GET delegates to POST so request.data can carry auth in body
    def get(self, request):
        return self.post(request)
