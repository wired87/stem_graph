import hashlib
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import SessionState, WorkspaceState

STATE_MAX_AGE = timedelta(days=1)
STATE_TTL = timedelta(minutes=30)


def hash_session(key: str) -> str:
    return hashlib.sha256(settings.SECRET_KEY.encode() + key.encode()).hexdigest()


def state_metadata(state, request=None):
    return {
        "id": str(state.pk),
        "workspace_id": str(state.workspace_id),
        "revision": state.revision,
        "created_at": state.created_at.isoformat(),
        "expires_at": state.expires_at.isoformat(),
        "rotated": bool(getattr(state, "was_rotated", False) or
                        getattr(request, "state_manager_rotated", False)),
    }


@transaction.atomic
def get_or_create_session_state(request):
    if not request.session.session_key:
        request.session.create()
    user = request.user if getattr(getattr(request, "user", None), "is_authenticated", False) else None
    now = timezone.now()
    session_hash = hash_session(request.session.session_key)
    state = SessionState.objects.select_for_update().filter(session_hash=session_hash).first()
    rotated = False
    if state is not None and now - state.created_at >= STATE_MAX_AGE:
        workspace_id = state.workspace_id
        state.delete()
        WorkspaceState.objects.filter(pk=workspace_id).delete()
        state = None
        rotated = True
    if state is None:
        workspace = WorkspaceState.objects.create(owner=user, name=f"session:{session_hash[:32]}")
        state = SessionState.objects.create(
            owner=user, workspace=workspace, session_hash=session_hash,
            expires_at=now + STATE_TTL,
        )
    else:
        changed = ["expires_at", "updated_at"]
        state.expires_at = now + STATE_TTL
        if state.owner_id is None and user is not None:
            state.owner = user
            state.workspace.owner = user
            state.workspace.save(update_fields=("owner", "updated_at"))
            changed.append("owner")
        state.save(update_fields=changed)
    state.was_rotated = rotated
    if rotated:
        request.state_manager_rotated = True
    return state
