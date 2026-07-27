"""JWT helpers — SimpleJWT token pair (ChatBotBackend pattern)."""
from __future__ import annotations

from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from accounts.serializers import EmailTokenObtainPairSerializer


def get_jwt_token_pair(email: str, password: str) -> dict:
    serializer = EmailTokenObtainPairSerializer(data={"email": email, "password": password})
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)


def safe_get_jwt_token_pair(email: str, password: str) -> dict | None:
    try:
        return get_jwt_token_pair(email, password)
    except (TokenError, InvalidToken, Exception):
        return None
