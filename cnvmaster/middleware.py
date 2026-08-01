from __future__ import annotations

import time
import uuid

from django.shortcuts import render
from django.utils.cache import patch_vary_headers
from rest_framework.response import Response


class RequestResponseMiddleware:
    """Classify HTML/HTMX/JSON requests and add non-breaking response metadata."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.perf_counter()
        request.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        accept = request.headers.get("Accept", "").lower()
        content_type = (request.content_type or "").lower()
        request.is_htmx = request.headers.get("HX-Request", "").lower() == "true"
        explicit_json = "application/json" in accept or content_type.startswith("application/json")
        request.wants_html = request.is_htmx or ("text/html" in accept and not explicit_json)
        request.wants_json = explicit_json or (
            not request.wants_html
            and request.path.startswith(("/api/", "/protein/", "/drug/"))
        )

        response = self.get_response(request)
        data = getattr(response, "data", None)
        if isinstance(data, dict):
            status_code = int(getattr(response, "status_code", 200) or 200)
            data.setdefault("success", status_code < 400)
            data.setdefault("status_code", status_code)
            data.setdefault("request_id", request.request_id)
            if status_code >= 400:
                message = data.get("message") or data.get("detail") or data.get("error")
                if message is not None:
                    data.setdefault("message", str(message))
                    data.setdefault("error", str(message))
        response["X-Request-ID"] = request.request_id
        response["Server-Timing"] = f'app;dur={(time.perf_counter() - started) * 1000:.2f}'
        patch_vary_headers(response, ("Accept", "HX-Request"))
        return response


class HybridResponseMixin:
    @staticmethod
    def _django_request(request):
        return getattr(request, "_request", request)

    def is_html_request(self, request) -> bool:
        django_request = self._django_request(request)
        if getattr(django_request, "is_htmx", False):
            return True
        if getattr(django_request, "wants_json", False):
            return False
        if getattr(django_request, "wants_html", False):
            return True
        return "text/html" in django_request.META.get("HTTP_ACCEPT", "").lower()

    def component_response(self, request, template_name, context, *, status_code=200):
        if self.is_html_request(request):
            return render(self._django_request(request), template_name, context, status=status_code)
        return Response(context, status=status_code)

    def validation_error_response(self, request, template_name, errors):
        return self.component_response(request, template_name, {
            "success": False,
            "message": "Input validation failed.",
            "errors": errors,
            "form_errors": errors,
        }, status_code=400)
