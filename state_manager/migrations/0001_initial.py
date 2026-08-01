import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="WorkspaceState",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(default="default", max_length=120)),
                ("data", models.JSONField(blank=True, default=dict)),
                ("revision", models.PositiveBigIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                             related_name="workspace_states", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-updated_at",)},
        ),
        migrations.CreateModel(
            name="ComponentState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("component_key", models.CharField(max_length=180)),
                ("data", models.JSONField(blank=True, default=dict)),
                ("revision", models.PositiveBigIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                 related_name="components", to="state_manager.workspacestate")),
            ],
            options={"ordering": ("component_key",)},
        ),
        migrations.CreateModel(
            name="SessionState",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("session_hash", models.CharField(db_index=True, max_length=64, unique=True)),
                ("data", models.JSONField(blank=True, default=dict)),
                ("revision", models.PositiveBigIntegerField(default=0)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                             related_name="session_states", to=settings.AUTH_USER_MODEL)),
                ("workspace", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                                                    related_name="session_state", to="state_manager.workspacestate")),
            ],
            options={"ordering": ("-updated_at",)},
        ),
        migrations.AddConstraint(
            model_name="workspacestate",
            constraint=models.UniqueConstraint(fields=("owner", "name"),
                                               name="state_manager_unique_owner_workspace_name"),
        ),
        migrations.AddConstraint(
            model_name="componentstate",
            constraint=models.UniqueConstraint(fields=("workspace", "component_key"),
                                               name="state_manager_unique_workspace_component"),
        ),
    ]
