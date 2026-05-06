import time

from django.core.management.base import BaseCommand

from apps.discoveries import services as discovery_services
from apps.risk import services as risk_services


class Command(BaseCommand):
    help = "Process queued background jobs."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Keep polling for queued jobs.")
        parser.add_argument("--sleep", type=float, default=2.0, help="Sleep seconds between empty polls in loop mode.")

    def handle(self, *args, **options):
        loop = options["loop"]
        sleep_sec = options["sleep"]
        processors = [
            ("discovery", discovery_services.process_next_discovery_task),
            ("recompute", risk_services.process_next_recompute_task),
        ]

        while True:
            processed = False
            for task_name, processor in processors:
                result = processor()
                if result is not None:
                    processed = True
                    self.stdout.write(self.style.SUCCESS(f"processed {task_name} task: {result}"))

            if not loop:
                break
            if not processed:
                time.sleep(sleep_sec)
