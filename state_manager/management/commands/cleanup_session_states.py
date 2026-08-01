from django.core.management.base import BaseCommand
from django.utils import timezone

from state_manager.models import SessionState, WorkspaceState


class Command(BaseCommand):
    help = "Delete expired state-manager sessions and their workspaces."

    def handle(self, *args, **options):
        states = SessionState.objects.filter(expires_at__lt=timezone.now())
        workspace_ids = list(states.values_list("workspace_id", flat=True))
        count = states.count()
        states.delete()
        WorkspaceState.objects.filter(pk__in=workspace_ids).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} expired session states."))
