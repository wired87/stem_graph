from rest_framework import serializers

from .models import ComponentState, WorkspaceState


class ComponentStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComponentState
        fields = ("component_key", "data", "revision", "updated_at")
        read_only_fields = fields


class WorkspaceStateSerializer(serializers.ModelSerializer):
    components = ComponentStateSerializer(many=True, read_only=True)

    class Meta:
        model = WorkspaceState
        fields = ("id", "name", "data", "revision", "components", "created_at", "updated_at")
        read_only_fields = ("id", "data", "revision", "components", "created_at", "updated_at")


class ComponentStateUpdateSerializer(serializers.Serializer):
    data = serializers.JSONField()
    expected_revision = serializers.IntegerField(required=False, min_value=0)
