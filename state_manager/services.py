from __future__ import annotations

from collections.abc import Mapping
from django.db import transaction

from .models import ComponentState, WorkspaceState
from .registry import registry


class RevisionConflict(RuntimeError):
    pass


@transaction.atomic
def update_component_state(*, workspace: WorkspaceState, component_key: str,
                           data: Mapping, expected_revision: int | None = None):
    registry.get(component_key)
    locked_workspace = WorkspaceState.objects.select_for_update().get(pk=workspace.pk)
    if expected_revision is not None and locked_workspace.revision != expected_revision:
        raise RevisionConflict(
            f"Expected workspace revision {expected_revision}, got {locked_workspace.revision}"
        )
    component, _ = ComponentState.objects.select_for_update().get_or_create(
        workspace=locked_workspace, component_key=component_key
    )
    component.data = dict(data)
    component.revision += 1
    component.save(update_fields=("data", "revision", "updated_at"))
    workspace_data = dict(locked_workspace.data)
    workspace_data[component_key] = component.data
    locked_workspace.data = workspace_data
    locked_workspace.revision += 1
    locked_workspace.save(update_fields=("data", "revision", "updated_at"))
    return component, locked_workspace


def resolve_required_data(*, workspace: WorkspaceState, component_key: str):
    contract = registry.get(component_key)
    states = {state.component_key: state.data for state in workspace.components.all()}
    resolved, missing = {}, []
    for data_key in sorted(contract.requires):
        provider = registry.provider_for(data_key)
        if provider is None or provider.key not in states or data_key not in states[provider.key]:
            missing.append(data_key)
        else:
            resolved[data_key] = states[provider.key][data_key]
    return resolved, tuple(missing)
