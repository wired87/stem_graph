# Shared GBucket helper: user id from request.data with TEST_USER_ID fallback
import os

from file_master._g_storage.storage import GBucket


# Resolve user id/auth from body, else env test user
def user_id_from_request(request):
    # user_id or auth field from request body
    return request.data.get('user_id') or request.data.get('auth') or os.getenv('TEST_USER_ID', '')


# Build user-scoped GCS prefix
def user_prefix(request):
    # prefix like "uid123/"
    user_id = user_id_from_request(request)
    return f"{user_id}/" if user_id else ""


# Single GBucket instance factory per call
def get_bucket():
    return GBucket()
