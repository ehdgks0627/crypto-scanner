from django.utils import timezone


TARGET_CONTEXT = {
    "sensitivity": "high",
    "lifespan_years": 10,
    "criticality": "high",
    "exposure": "internal_network",
    "service_role": "web-frontend",
}


def create_target(**overrides):
    from apps.targets.models import Target

    values = {
        "host": "web.testbed.local",
        "ip": None,
        "port": 443,
        "protocol_hint": "TLS",
        "sni": None,
        "transport": "TCP",
        "agent_enabled": True,
        "agent_url": None,
        "context": TARGET_CONTEXT,
    }
    values.update(overrides)
    return Target.objects.create(**values)


def create_async_job(**overrides):
    from apps.jobs.models import AsyncJob

    values = {
        "kind": "scan_job",
        "status": "PENDING",
        "resource_id": None,
        "request_payload": {},
        "progress": None,
        "result": None,
        "error": None,
    }
    values.update(overrides)
    return AsyncJob.objects.create(**values)


def create_scan_job(async_job=None, **overrides):
    from apps.jobs.models import ScanJob

    if async_job is None:
        async_job = create_async_job(kind="scan_job")
    values = {
        "async_job": async_job,
        "target_ids": [],
        "scanner_selection": ["network"],
    }
    values.update(overrides)
    scan_job = ScanJob.objects.create(**values)
    if async_job.resource_id != scan_job.id:
        async_job.resource_id = scan_job.id
        async_job.save(update_fields=["resource_id"])
    return scan_job


def create_snapshot(**overrides):
    from apps.snapshots.models import CbomSnapshot

    values = {
        "serial_number": "urn:uuid:test-snapshot",
        "summary": {},
        "validation_errors": [],
        "cbom_json": {"bomFormat": "CycloneDX", "specVersion": "1.6"},
    }
    values.update(overrides)
    return CbomSnapshot.objects.create(**values)


def create_asset(snapshot=None, target=None, **overrides):
    from apps.assets.models import Asset

    if snapshot is None:
        snapshot = create_snapshot()
    if target is None:
        target = create_target(host=f"target-{Asset.objects.count() + 1}.testbed.local")
    values = {
        "snapshot": snapshot,
        "target": target,
        "name": "web certificate",
        "asset_class": "crypto",
        "asset_type": "certificate",
        "natural_key": f"certificate:{timezone.now().timestamp()}",
        "algorithm": "RSA-2048",
        "algorithm_family": "RSA",
    }
    values.update(overrides)
    return Asset.objects.create(**values)


def create_risk_score(asset, **overrides):
    from apps.risk.models import RiskScore

    values = {
        "snapshot": asset.snapshot,
        "asset": asset,
        "score": 95.0,
        "tier": "CRITICAL",
        "factors": {"A": 0.95},
    }
    values.update(overrides)
    return RiskScore.objects.create(**values)


def assert_job_envelope(body):
    assert {
        "id",
        "kind",
        "resource",
        "status",
        "progress",
        "started_at",
        "cancel_requested_at",
        "finished_at",
        "result",
        "error",
    } <= set(body)
