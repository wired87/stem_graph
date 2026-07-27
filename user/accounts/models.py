"""
Django user models — JWT auth in SQLite; billing state in Firebase RTDB (fb_core).

Prompt: replace local database operations with firebase implementation following same schema.
"""
from __future__ import annotations

import random
import string

from django.contrib.auth.models import AbstractUser
from django.db import models

from accounts.managers import LighterUserManager


def _generate_public_uid(length: int = 20) -> str:
    alphabet = string.ascii_lowercase + string.digits
    while True:
        candidate = "".join(random.choices(alphabet, k=length))
        if not LighterUser.objects.filter(public_uid=candidate).exists():
            return candidate


class LighterUser(AbstractUser):
    """Email-login user with stable public uid for API billing keys."""

    email = models.EmailField(max_length=255, unique=True)
    public_uid = models.CharField(max_length=32, unique=True, editable=False, blank=True)
    objects = LighterUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = "accounts_user"

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.email
        if not self.public_uid:
            self.public_uid = _generate_public_uid()
        super().save(*args, **kwargs)


class UserWallet(models.Model):
    """Per-user env billing state (credits, free-tier counters, output metadata)."""

    billing_key = models.CharField(max_length=128, db_index=True)
    env_id = models.CharField(max_length=64, default="default")
    credits_balance = models.IntegerField(default=0)
    free_daily = models.JSONField(default=dict, blank=True)
    free_monthly = models.JSONField(default=dict, blank=True)
    profile = models.JSONField(default=dict, blank=True)
    output = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    history = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_wallet"
        unique_together = (("billing_key", "env_id"),)


class SystemKv(models.Model):
    """System-level key/value (webhook locks etc.) — replaces Firebase system paths."""

    key = models.CharField(max_length=255, unique=True)
    value = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_system_kv"


class UsageHistoryEntry(models.Model):
    billing_key = models.CharField(max_length=128, db_index=True)
    env_id = models.CharField(max_length=64, default="default")
    action = models.CharField(max_length=128)
    status = models.CharField(max_length=32, default="ok")
    request_id = models.CharField(max_length=128, blank=True, default="")
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_usage_history"
        indexes = [models.Index(fields=["billing_key", "-created_at"])]
