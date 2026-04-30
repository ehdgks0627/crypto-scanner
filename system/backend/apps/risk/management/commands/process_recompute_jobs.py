import time

from django.core.management.base import BaseCommand

from apps.risk import services


class Command(BaseCommand):
    help = "Process queued risk recompute jobs."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Keep polling for recompute tasks.")
        parser.add_argument("--sleep", type=float, default=2.0, help="Seconds to sleep between empty polls.")

    def handle(self, *args, **options):
        loop = options["loop"]
        sleep_seconds = options["sleep"]

        while True:
            result = services.process_next_recompute_task()
            if result:
                self.stdout.write(self.style.SUCCESS(f"processed recompute task: {result}"))
                continue
            if not loop:
                self.stdout.write("no queued recompute tasks")
                return
            time.sleep(sleep_seconds)
