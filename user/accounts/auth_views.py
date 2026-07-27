"""
Auth API views — register, login, refresh (ChatBotBackend validation style).

Prompt: Ensure user objects get saved, edited and validated on server side using the fb_core rtdb package.
Prompt: replace google auth with email password built on ChatBotBackend validation approach.
"""
from __future__ import annotations

from django.contrib.auth import authenticate
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.auth_validators import validate_login_payload, validate_registration_payload
from accounts.billing import sync_user_session
from accounts.jwt_tokens import get_jwt_token_pair
from accounts.models import LighterUser
from accounts.serializers import EmailTokenObtainPairSerializer, EmailTokenRefreshSerializer
from fb_core.storage import ensure_user_bucket_folder


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")
        ok, message, code = validate_registration_payload(email, password)

        if not ok:
            return Response({"success": False, "status_code": code, "message": message, "error": message}, status=400)

        email_clean = email.strip().lower()

        if LighterUser.objects.filter(email=email_clean).exists():
            return Response(
                {"success": False, "status_code": 20, "message": "Email already exists", "error": "Email already exists"},
                status=400,
            )

        user = LighterUser.objects.create_user(email=email_clean, password=password)

        sync_user_session(
            user.public_uid,
            email=user.email,
            display_name=user.get_full_name() or None,
            source="django",
            action="auth.register",
        )

        ensure_user_bucket_folder(user_id=user.public_uid)
        tokens = get_jwt_token_pair(email_clean, password)

        return Response(
            {
                "success": True,
                "status_code": 200,
                "message": "Account successfully created",
                "user_id": user.public_uid,
                "uid": user.public_uid,
                "email": user.email,
                "access": tokens["access"],
                "refresh": tokens["refresh"],
                "user": {
                    "uid": user.public_uid,
                    "email": user.email,
                    "displayName": user.get_full_name() or None,
                    "isAnonymous": False,
                },
            }
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")
        ok, message, code = validate_login_payload(email, password)
        if not ok:
            return Response({"success": False, "status_code": code, "message": message, "error": message}, status=400)
        email_clean = email.strip().lower()
        user = authenticate(request, username=email_clean, password=password)
        if not user:
            return Response(
                {
                    "success": False,
                    "status_code": 23,
                    "message": "Credentials are not valid. Please try again or contact the support",
                    "error": "Invalid credentials",
                },
                status=401,
            )
        tokens = get_jwt_token_pair(email_clean, password)
        sync_user_session(
            user.public_uid,
            email=user.email,
            display_name=user.get_full_name() or None,
            source="django",
            action="auth.login",
        )
        return Response(
            {
                "success": True,
                "status_code": 200,
                "message": "Login successfully finished",
                "user_id": user.public_uid,
                "uid": user.public_uid,
                "email": user.email,
                "access": tokens["access"],
                "refresh": tokens["refresh"],
                "user": {
                    "uid": user.public_uid,
                    "email": user.email,
                    "displayName": user.get_full_name() or None,
                    "isAnonymous": False,
                },
            }
        )


class EmailTokenObtainPairView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = EmailTokenObtainPairSerializer


class EmailTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
    serializer_class = EmailTokenRefreshSerializer
