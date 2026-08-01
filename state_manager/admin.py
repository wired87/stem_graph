from django.contrib import admin

from .models import ComponentState, SessionState, WorkspaceState


class ComponentStateInline(admin.TabularInline):
    model = ComponentState
    extra = 0
    readonly_fields = ("revision", "updated_at")


@admin.register(WorkspaceState)
class WorkspaceStateAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "name", "revision", "updated_at")
    inlines = (ComponentStateInline,)


@admin.register(SessionState)
class SessionStateAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "workspace", "revision", "expires_at")
