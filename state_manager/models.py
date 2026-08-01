import uuid

from django.conf import settings
from django.db import models


class WorkspaceState(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
        related_name="workspace_states",
    )
    name = models.CharField(max_length=120, default="default")
    data = models.JSONField(default=dict, blank=True)
    revision = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        constraints = [models.UniqueConstraint(
            fields=("owner", "name"), name="state_manager_unique_owner_workspace_name"
        )]


class ComponentState(models.Model):
    workspace = models.ForeignKey(WorkspaceState, on_delete=models.CASCADE, related_name="components")
    component_key = models.CharField(max_length=180)
    data = models.JSONField(default=dict, blank=True)
    revision = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("component_key",)
        constraints = [models.UniqueConstraint(
            fields=("workspace", "component_key"), name="state_manager_unique_workspace_component"
        )]


class SessionState(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
        related_name="session_states",
    )
    workspace = models.OneToOneField(WorkspaceState, on_delete=models.CASCADE, related_name="session_state")
    session_hash = models.CharField(max_length=64, unique=True, db_index=True)
    data = models.JSONField(default=dict, blank=True)
    revision = models.PositiveBigIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def merge_validated_data(self, *, route, component_key, serializer_path, payload):
        state_data = dict(self.data)
        routes = dict(state_data.get("routes", {}))
        routes[str(route)] = payload
        state_data["routes"] = routes
        if serializer_path:
            serializers = dict(state_data.get("serializers", {}))
            serializers[str(serializer_path)] = payload
            state_data["serializers"] = serializers
        if component_key:
            components = dict(state_data.get("components", {}))
            components[str(component_key)] = payload
            state_data["components"] = components
        self.data = state_data
        self.revision += 1
