from collections.abc import Mapping
from decimal import Decimal
from uuid import UUID

from django.db import transaction

from .registry import registry
from .session import get_or_create_session_state, state_metadata

SENSITIVE = {"password", "password1", "password2", "csrfmiddlewaretoken", "token", "secret"}


def _safe_value(value):
    if hasattr(value, "read"):
        return {"name": getattr(value, "name", "upload"), "size": getattr(value, "size", None)}
    if isinstance(value, Mapping):
        return {str(key): _safe_value(item) for key, item in value.items()
                if str(key).lower() not in SENSITIVE}
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _component_for_request(request):
    view_class = getattr(getattr(request, "resolver_match", None), "func", None)
    view_class = getattr(view_class, "view_class", None)
    for contract in registry.all():
        if contract.view_class is view_class:
            return contract.key
    return None


class StateCaptureMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        state = get_or_create_session_state(request)
        request.state_manager_state = state
        response = self.get_response(request)
        metadata = state_metadata(state, request=request)
        response["X-State-ID"] = metadata["id"]
        response["X-State-Revision"] = str(metadata["revision"])
        response["X-State-Rotated"] = "true" if metadata["rotated"] else "false"
        response_data = getattr(response, "data", None)
        if isinstance(response_data, dict):
            response_data["state"] = metadata
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"} or response.status_code >= 400:
            return response
        validated = getattr(request, "_state_manager_validated_payloads", None) or []
        if not validated:
            return response
        captured = validated[-1]
        payload = _safe_value(captured.get("data"))
        route = getattr(getattr(request, "resolver_match", None), "view_name", None) or request.path
        component_key = _component_for_request(request)
        with transaction.atomic():
            locked = type(state).objects.select_for_update().get(pk=state.pk)
            locked.merge_validated_data(
                route=route,
                component_key=component_key,
                serializer_path=captured.get("serializer"),
                payload=payload if isinstance(payload, dict) else {},
            )
            locked.save(update_fields=("data", "revision", "updated_at"))
        return response
