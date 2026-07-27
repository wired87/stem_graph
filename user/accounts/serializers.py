"""
Custom JWT serializer — email field instead of username.

Prompt: Ensure user objects get saved, edited and validated on server side using the fb_core rtdb package.
"""
from __future__ import annotations

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.billing import sync_user_session
from accounts.models import LighterUser


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = "email"

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["uid"] = user.public_uid
        token["email"] = user.email
        return token


def _enrich_access_token(access, user_id) -> None:
    """Attach public uid + email to refreshed access tokens (same shape as login)."""
    user = LighterUser.objects.filter(pk=user_id).first()
    if not user:
        return
    access["uid"] = user.public_uid
    access["email"] = user.email


class EmailTokenRefreshSerializer(TokenRefreshSerializer):
    """Refresh access tokens and return rotated refresh when configured."""

    def validate(self, attrs):
        refresh = RefreshToken(attrs["refresh"])
        user_id = refresh.get("user_id")
        access = refresh.access_token
        _enrich_access_token(access, user_id)

        data = {"access": str(access)}

        # Honor ROTATE_REFRESH_TOKENS / BLACKLIST_AFTER_ROTATION from settings.
        if api_settings.ROTATE_REFRESH_TOKENS:
            if api_settings.BLACKLIST_AFTER_ROTATION:
                refresh.blacklist()
            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()
            data["refresh"] = str(refresh)

        user = LighterUser.objects.filter(pk=user_id).first()
        if user:
            sync_user_session(
                user.public_uid,
                email=user.email,
                display_name=user.get_full_name() or None,
                source="django",
                action="auth.token_refresh",
            )

        return data
