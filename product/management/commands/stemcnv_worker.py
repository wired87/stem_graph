import time

from django.core.management.base import BaseCommand

from product.models import StemCNVRun
from product.stemcnv_docker import StemCNVDockerError, cancel_run, claim_and_launch_next, get_run


class Command(BaseCommand):
    help = "Run the PostgreSQL-backed StemCNV Docker worker"

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--poll-seconds", type=float, default=3.0)

    def handle(self, *args, **options):
        while True:
            for run_id in StemCNVRun.objects.filter(status="cancelling").values_list("run_id", flat=True):
                cancel_run(run_id)
            for run_id in StemCNVRun.objects.filter(status="running").values_list("run_id", flat=True):
                try:
                    get_run(run_id)
                except (FileNotFoundError, StemCNVDockerError) as exc:
                    self.stderr.write(f"{run_id}: {exc}")
            launched = claim_and_launch_next()
            if launched:
                self.stdout.write(f"launched {launched['run_id']}")
            if options["once"]:
                return
            time.sleep(options["poll_seconds"])
