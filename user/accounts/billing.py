"""
Firebase RTDB billing facade — drop-in for legacy FirebaseAdmin imports.

Prompt: Ensure user objects get saved, edited and validated on server side using the fb_core rtdb package.
"""
from __future__ import annotations

from fb_core.db_admin import (
    FirebaseAdmin,
    _ensure_user_exists_in_auth,
    _normalize_email,
    record_purchase_event,
    resolve_billing_user_id,
    sync_user_session,
)

# Legacy import names used across lighter_app / api_handlers / accounts.auth_views
BillingAdmin = FirebaseAdmin

__all__ = [
    "BillingAdmin",
    "FirebaseAdmin",
    "_ensure_user_exists_in_auth",
    "_normalize_email",
    "record_purchase_event",
    "resolve_billing_user_id",
    "sync_user_session",
]
