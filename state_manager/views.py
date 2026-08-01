from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .registry import registry
from .serializers import ComponentStateUpdateSerializer, WorkspaceStateSerializer
from .services import RevisionConflict, resolve_required_data, update_component_state
from .session import get_or_create_session_state, state_metadata


class SessionStateView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request):
        state = get_or_create_session_state(request)
        return Response({**state_metadata(state, request=request),
                         "workspace": WorkspaceStateSerializer(state.workspace).data})


class ComponentStateView(APIView):
    permission_classes = (AllowAny,)

    def put(self, request, component_key):
        state = get_or_create_session_state(request)
        serializer = ComponentStateUpdateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            component, workspace = update_component_state(
                workspace=state.workspace,
                component_key=component_key,
                data=serializer.validated_data["data"],
                expected_revision=serializer.validated_data.get("expected_revision"),
            )
        except RevisionConflict as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response({
            "component": component.component_key,
            "data": component.data,
            "component_revision": component.revision,
            "workspace_revision": workspace.revision,
            "dependents": sorted(registry.dependents(component_key)),
        })


class ComponentRequirementsView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request, component_key):
        state = get_or_create_session_state(request)
        resolved, missing = resolve_required_data(
            workspace=state.workspace, component_key=component_key
        )
        return Response({"data": resolved, "missing": missing})


class ComponentRegistryView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request):
        return Response({"components": [{
            "key": item.key,
            "provides": sorted(item.provides),
            "requires": sorted(item.requires),
            "dependencies": sorted(registry.dependencies(item.key)),
        } for item in registry.all()], "order": registry.topological_order()})
