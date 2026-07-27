"""
Run-id generator for BETSE simulation uploads.

Prompt: implement _betse and betse_cfg_wizard routes to the server infrastructure
(paste routes, adapt settings).
"""
from __future__ import annotations

import uuid


def generate_id() -> str:
    """CHAR: short opaque id for betse_data/<run_id>/ folders."""
    return uuid.uuid4().hex
