# Shared GBucket helper: JWT uid from Authorization header with TEST_USER_ID fallback
import os

from rest_framework import status
from rest_framework.response import Response

from file_master._g_storage.storage import GBucket
from accounts.billing import FirebaseAdmin
from accounts.jwt_auth import verify_jwt_bearer


# Resolve authenticated user id from JWT Bearer token
def user_id_from_request(request):
    # JWT claims from Authorization: Bearer <access>
    claims = verify_jwt_bearer(request.headers.get("Authorization"))
    if claims and claims.get("uid"):
        return claims["uid"]
    # optional body override / local test fallback
    return request.data.get("user_id") or request.data.get("auth") or os.getenv("TEST_USER_ID", "")


# Return uid or 401 Response when auth is required
def require_user_id(request):
    # authenticated billing key for user-scoped storage
    user_id = user_id_from_request(request)
    if not user_id:
        return None, Response(
            {
                "success": False,
                "status_code": 401,
                "message": "Unauthorized",
                "error": "Valid JWT Bearer token required",
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )
    return user_id, None


# Build user-scoped GCS prefix
def user_prefix(request):
    # prefix like "uid123/"
    user_id = user_id_from_request(request)
    return f"{user_id}/" if user_id else ""


# Single GBucket instance factory per call
def get_bucket():
    return GBucket()


# Record file_master action in Firebase RTDB history (accounts/billing pattern)
def record_file_history(request, action: str, file_name: str, status_value: str = "ok", details=None):
    # skip when caller did not authenticate
    user_id, _ = require_user_id(request)
    if not user_id:
        return
    # FirebaseAdmin history event for audit trail
    admin = FirebaseAdmin(user_id)
    event_details = {"file_name": file_name}
    if isinstance(details, dict):
        event_details.update(details)
    admin.record_history_event(action=action, status=status_value, details=event_details)
