"""Capture only successful DRF serializer validation results."""
from rest_framework.serializers import BaseSerializer

_installed = False


def install_serializer_capture():
    global _installed
    if _installed:
        return
    original = BaseSerializer.is_valid

    def is_valid(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        if result:
            request = getattr(self, "context", {}).get("request")
            django_request = getattr(request, "_request", request)
            if django_request is not None:
                payloads = getattr(django_request, "_state_manager_validated_payloads", None)
                if payloads is None:
                    payloads = []
                    django_request._state_manager_validated_payloads = payloads
                payloads.append({
                    "serializer": f"{self.__class__.__module__}.{self.__class__.__qualname__}",
                    "data": self.validated_data,
                })
        return result

    BaseSerializer.is_valid = is_valid
    _installed = True
