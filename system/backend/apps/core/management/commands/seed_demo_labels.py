from django.core.management.base import BaseCommand
from django.db import transaction

from apps.assets.models import Asset, AssetContextOverride
from apps.core.management.commands.seed_testbed_demo import SERIAL_PREFIX
from apps.targets.models import Target, default_context


DEMO_HOST_LABELS = [
    {
        "alias": "srv-01",
        "target": {"host": "api-gateway.testbed.local", "port": 8443, "transport": "TCP"},
        "display_name": "srv-01 - 외부 결제 API",
        "role": "edge-proxy",
        "data_classes": ["PII", "payment"],
        "partners": ["PG-A"],
        "retention": "7y",
        "context": {
            "sensitivity": "critical",
            "lifespan_years": 7,
            "criticality": "critical",
            "exposure": "public_internet",
            "service_role": "edge-proxy",
        },
    },
]


class Command(BaseCommand):
    help = "Seed deterministic host labels used by the final presentation demo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--serial-prefix",
            default=SERIAL_PREFIX,
            help="CBOM snapshot serial prefix whose assets should receive the label metadata.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        serial_prefix = options["serial_prefix"]
        targets_updated = 0
        assets_updated = 0
        missing = []

        for label in DEMO_HOST_LABELS:
            selector = label["target"]
            target = Target.objects.filter(**selector).first()
            if target is None:
                missing.append(f"{selector['host']}:{selector['port']}/{selector['transport']}")
                continue

            target.context = _merged_target_context(target.context, label)
            target.display_name = label["display_name"]
            target.save(update_fields=["context", "display_name", "updated_at"])
            targets_updated += 1

            for asset in Asset.objects.filter(
                target=target,
                snapshot__serial_number__startswith=serial_prefix,
            ).select_related("snapshot"):
                asset.metadata = _merged_asset_metadata(asset.metadata, label)
                asset.save(update_fields=["metadata", "updated_at"])
                AssetContextOverride.objects.update_or_create(
                    asset=asset,
                    defaults={
                        **label["context"],
                        "override_keys": ["sensitivity", "lifespan_years", "criticality", "exposure", "service_role"],
                    },
                )
                assets_updated += 1

        if missing:
            self.stdout.write(self.style.WARNING(f"Missing demo label targets: {', '.join(missing)}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded demo labels: targets={targets_updated}, assets={assets_updated}, serial_prefix={serial_prefix}"
            )
        )


def _merged_target_context(current: dict | None, label: dict) -> dict:
    context = {**default_context(), **(current or {})}
    context.update(label["context"])
    context.update(
        {
            "host_alias": label["alias"],
            "demo_label": {
                "role": label["role"],
                "data_classes": label["data_classes"],
                "partners": label["partners"],
                "retention": label["retention"],
            },
        }
    )
    return context


def _merged_asset_metadata(current: dict | None, label: dict) -> dict:
    metadata = {**(current or {})}
    metadata.update(
        {
            "host_alias": label["alias"],
            "host_role": label["role"],
            "data_tags": label["data_classes"],
            "partners": label["partners"],
            "retention_policy": label["retention"],
        }
    )
    discovered_by = set(metadata.get("discovered_by") or [])
    discovered_by.update(["discovery_agent", "host_agent"])
    metadata["discovered_by"] = sorted(discovered_by)
    return metadata
