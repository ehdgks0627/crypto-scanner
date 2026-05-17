import pytest

from tests.api.factories import create_asset, create_async_job, create_risk_score, create_scan_job, create_snapshot, create_target


pytestmark = pytest.mark.django_db


def test_api_settings_001_delete_snapshot_results_keeps_targets(client):
    from apps.assets.models import Asset
    from apps.jobs.models import QueuedTask, ScanRunLog, ScanJob
    from apps.risk.models import RiskScore
    from apps.snapshots.models import CbomSnapshot
    from apps.targets.models import Target

    target = create_target()
    scan_async_job = create_async_job(kind="scan_job", status="COMPLETED")
    scan_job = create_scan_job(async_job=scan_async_job, target_ids=[target.id], scanner_selection=["network"])
    snapshot = create_snapshot(scan_job=scan_job)
    asset = create_asset(snapshot=snapshot, target=target)
    create_risk_score(asset)
    ScanRunLog.objects.create(async_job=scan_async_job, target=target, scanner_kind="network", status="SUCCESS", findings_count=1)
    QueuedTask.objects.create(async_job=scan_async_job, task_name="scan_job", payload={}, status=QueuedTask.COMPLETED)
    create_async_job(kind="recompute", status="COMPLETED", result={"updated_scores_count": 1})

    response = client.delete("/api/settings/snapshots")

    assert response.status_code == 200
    deleted = response.json()["deleted"]
    assert {
        "snapshots": 1,
        "assets": 1,
        "risk_scores": 1,
        "jobs": 2,
        "scan_jobs": 1,
        "scan_logs": 1,
        "queued_tasks": 1,
    }.items() <= deleted.items()
    assert CbomSnapshot.objects.count() == 0
    assert Asset.objects.count() == 0
    assert RiskScore.objects.count() == 0
    assert ScanJob.objects.count() == 0
    assert Target.objects.count() == 1


def test_api_settings_002_delete_scan_targets_keeps_snapshots_and_unlinks_endpoints(client):
    from apps.discoveries.models import DiscoveredEndpoint, Discovery
    from apps.jobs.models import AsyncJob
    from apps.snapshots.models import CbomSnapshot
    from apps.targets.models import Target

    target = create_target()
    snapshot = create_snapshot()
    create_asset(snapshot=snapshot, target=target)
    discovery_job = AsyncJob.objects.create(kind="discovery", status="COMPLETED")
    discovery = Discovery.objects.create(async_job=discovery_job, cidr="10.0.0.0/24", scope_type="cidr", scope_value="10.0.0.0/24")
    endpoint = DiscoveredEndpoint.objects.create(
        discovery=discovery,
        host=target.host,
        port=target.port,
        transport=target.transport,
        detected_protocol="TLS",
        suggested_protocol_hint="TLS",
        promoted=True,
        target=target,
    )

    response = client.delete("/api/settings/scan-targets")

    assert response.status_code == 200
    assert response.json()["deleted"] == {"scan_targets": 1, "discovery_endpoint_links": 1}
    assert Target.objects.count() == 0
    assert CbomSnapshot.objects.count() == 1
    endpoint.refresh_from_db()
    assert endpoint.target_id is None
    assert endpoint.promoted is False
