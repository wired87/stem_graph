"""
Auth input validation — ChatBotBackend-style checks + Django password validators.

Prompt: replace google auth with email password built on ChatBotBackend validation approach.
"""
from __future__ import annotations

from typing import Optional, Tuple

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


def _friendly_password_validation_message(messages) -> str:
    # AI: return short, non-technical password requirement errors
    if not messages:
        return "Password does not meet the requirements"
    joined = " ".join([str(m or "").strip() for m in messages if str(m or "").strip()]).strip()
    if not joined:
        return "Password does not meet the requirements"

    lowered = joined.lower()
    import re

    m = re.search(r"at least\s+(\d+)\s+character", lowered)
    if "too short" in lowered and m:
        return f"Minimum password length is {m.group(1)} characters"
    if "too common" in lowered:
        return "Password is too common. Please choose a more unique password"
    if "entirely numeric" in lowered or "only numbers" in lowered:
        return "Password cannot be only numbers"
    if "too similar" in lowered:
        return "Password is too similar to your personal information"
    return joined


def validate_registration_payload(email: Optional[str], password: Optional[str]) -> Tuple[bool, str, int]:
    if not email or not password or not isinstance(email, str) or not isinstance(password, str):
        return False, "Credentials missing", 26
    email_clean = email.strip().lower()
    if "@" not in email_clean:
        return False, "Invalid email address", 26
    try:
        from accounts.models import LighterUser

        validate_password(password, user=LighterUser(email=email_clean))
    except ValidationError as error:
        message = _friendly_password_validation_message(getattr(error, "messages", None))
        return False, message, 26
    return True, "", 200


def validate_login_payload(email: Optional[str], password: Optional[str]) -> Tuple[bool, str, int]:
    if not email or not password or not isinstance(email, str) or not isinstance(password, str):
        return False, "Credentials missing", 26
    return True, "", 200
