"""JWT identity resolution for legacy server handlers."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import LighterUser


def verify_jwt_bearer(authorization: Optional[str]) -> Optional[Dict[str, Any]]:
    raw = str(authorization or "").strip()
    if not raw.lower().startswith("bearer "):
        return None
    token = raw[7:].strip()
    if not token:
        return None
    try:
        access = AccessToken(token)
        uid = str(access.get("uid") or access.get("user_id") or "").strip() or None
        email = str(access.get("email") or "").strip().lower() or None
        if not uid and access.get("user_id"):
            user = LighterUser.objects.filter(pk=access["user_id"]).first()
            if user:
                uid = user.public_uid
                email = user.email
        if uid and not email:
            user = LighterUser.objects.filter(public_uid=uid).first()
            if user:
                email = user.email
        return {"uid": uid, "sub": uid, "email": email}
    except (TokenError, InvalidToken, Exception):
        return None


def resolve_user_from_claims(claims: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    uid = str(claims.get("uid") or claims.get("sub") or "").strip() or None
    email = str(claims.get("email") or "").strip().lower() or None
    return uid, email
