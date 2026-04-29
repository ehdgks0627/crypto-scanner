import pytest
from django.utils import timezone

from tests.api.factories import assert_job_envelope, create_async_job, create_scan_job, create_target


pytestmark = pytest.mark.django_db


def test_api_job_001_create_scan_job_returns_job_envelope(client):
    target = create_target()

    response = client.post(
        "/api/jobs",
        data={"target_ids": [target.id], "scanners": ["network"]},
        content_type="application/json",
    )

    assert response.status_code == 202
    body = response.json()
    assert_job_envelope(body)
    assert body["kind"] == "scan_job"
    assert body["resource"]["kind"] == "scan_job"
    assert body["status"] == "PENDING"
    assert body["progress"] is None
    assert body["result"] is None


def test_api_job_002_scan_enqueue_failure_returns_503(client, monkeypatch):
    from apps.jobs import services
    from apps.jobs.models import AsyncJob, ScanJob

    target = create_target()

    def fail_enqueue(scan_job):
        raise services.EnqueueUnavailable("queue unavailable")

    monkeypatch.setattr(services, "enqueue_scan_job", fail_enqueue)

    response = client.post(
        "/api/jobs",
        data={"target_ids": [target.id], "scanners": ["network"]},
        content_type="application/json",
    )

    assert response.status_code == 503
    assert response.json()["error"] == "service_unavailable"
    assert AsyncJob.objects.count() == 0


def test_api_job_002b_scan_create_rejects_unknown_scanner(client):
    target = create_target()

    response = client.post(
        "/api/jobs",
        data={"target_ids": [target.id], "scanners": ["unknown-scanner"]},
        content_type="application/json",
    )

    assert response.status_code == 422
    assert response.json()["error"] == "unprocessable"


def test_api_job_002c_list_jobs_filters_kind_and_validates_status(client):
    scan_job = create_async_job(kind="scan_job", status="COMPLETED")
    create_async_job(kind="discovery", status="COMPLETED")

    filtered = client.get("/api/jobs?kind=scan_job&status=COMPLETED&sort=id")
    invalid = client.get("/api/jobs?status=NOPE")

    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()["items"]] == [scan_job.id]
    assert invalid.status_code == 422


def test_api_job_003_list_jobs_returns_page(client):
    running_scan = create_async_job(kind="scan_job", status="RUNNING")
    create_async_job(kind="discovery", status="PENDING")
    create_async_job(kind="recompute", status="RUNNING")

    response = client.get("/api/jobs?status=RUNNING&limit=20&offset=0")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["offset"] == 0
    assert body["limit"] == 20
    assert {item["status"] for item in body["items"]} == {"RUNNING"}
    assert any(item["id"] == running_scan.id for item in body["items"])
    for item in body["items"]:
        assert_job_envelope(item)


def test_api_job_004_polling_returns_no_store_and_job_envelope(client):
    job = create_async_job(
        kind="scan_job",
        status="RUNNING",
        progress={"completed": 2, "total": 5},
    )

    response = client.get(f"/api/jobs/{job.id}")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    body = response.json()
    assert_job_envelope(body)
    assert body["progress"] == {"completed": 2, "total": 5}
    assert body["result"] is None


def test_api_job_005_completed_scan_job_returns_snapshot_result(client):
    job = create_async_job(kind="scan_job", status="COMPLETED", result={"snapshot_id": 56})

    response = client.get(f"/api/jobs/{job.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["result"]["snapshot_id"] == 56


def test_api_job_006_failed_job_returns_error_and_finished_at(client):
    finished_at = timezone.now()
    job = create_async_job(
        kind="discovery",
        status="FAILED",
        result=None,
        error="scanner timeout",
        finished_at=finished_at,
    )

    response = client.get(f"/api/jobs/{job.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["result"] is None
    assert body["error"] == "scanner timeout"
    assert body["finished_at"] is not None


@pytest.mark.parametrize("kind", ["scan_job", "discovery"])
@pytest.mark.parametrize("status", ["PENDING", "RUNNING"])
def test_api_job_007_scan_and_discovery_cancel_immediately_finishes_job(client, kind, status):
    from apps.jobs.models import QueuedTask

    job = create_async_job(kind=kind, status=status)
    queued_task = QueuedTask.objects.create(async_job=job, task_name=kind, payload={})

    response = client.post(f"/api/jobs/{job.id}/cancel")

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "CANCELLED"
    assert body["cancel_requested_at"] is not None
    assert body["finished_at"] is not None
    job.refresh_from_db()
    assert job.status == "CANCELLED"
    assert job.cancel_requested_at is not None
    assert job.finished_at is not None
    queued_task.refresh_from_db()
    assert queued_task.status == QueuedTask.CANCELLED
    assert queued_task.last_error == "cancel_requested"


def test_api_job_007b_discovery_cancel_syncs_domain_status(client):
    from apps.discoveries.models import Discovery

    job = create_async_job(kind="discovery", status="RUNNING", started_at=timezone.now())
    discovery = Discovery.objects.create(
        async_job=job,
        cidr="10.0.0.0/24",
        status="RUNNING",
        started_at=job.started_at,
    )
    job.resource_id = discovery.id
    job.save(update_fields=["resource_id"])

    response = client.post(f"/api/jobs/{job.id}/cancel")
    detail_response = client.get(f"/api/discoveries/{discovery.id}")
    list_response = client.get("/api/discoveries?status=CANCELLED")

    assert response.status_code == 202
    discovery.refresh_from_db()
    assert discovery.status == "CANCELLED"
    assert discovery.finished_at is not None
    assert discovery.error == "cancel_requested"
    assert detail_response.json()["status"] == "CANCELLED"
    assert detail_response.json()["progress"] is None
    assert any(item["id"] == discovery.id for item in list_response.json()["items"])


def test_api_job_007c_cancelled_job_cancel_is_idempotent(client):
    job = create_async_job(kind="scan_job", status="CANCELLED")

    first_response = client.post(f"/api/jobs/{job.id}/cancel")
    second_response = client.post(f"/api/jobs/{job.id}/cancel")

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert second_response.json()["status"] == "CANCELLED"


def test_api_job_008_pending_recompute_can_be_cancelled(client):
    job = create_async_job(kind="recompute", status="PENDING")

    response = client.post(f"/api/jobs/{job.id}/cancel")

    assert response.status_code == 202
    body = response.json()
    assert body["kind"] == "recompute"
    assert body["status"] == "CANCELLED"


def test_api_job_009_running_recompute_cannot_be_cancelled(client):
    job = create_async_job(kind="recompute", status="RUNNING")

    response = client.post(f"/api/jobs/{job.id}/cancel")

    assert response.status_code == 409
    body = response.json()
    assert body["error"] == "job_not_cancellable"
    assert body["details"] == {"job_id": job.id, "kind": "recompute", "status": "RUNNING"}


@pytest.mark.parametrize("status", ["COMPLETED", "FAILED"])
def test_api_job_010_terminal_job_cancel_returns_job_not_cancellable(client, status):
    job = create_async_job(kind="scan_job", status=status)

    response = client.post(f"/api/jobs/{job.id}/cancel")

    assert response.status_code == 409
    assert response.json()["error"] == "job_not_cancellable"


def test_api_job_011_cancel_missing_job_returns_not_found(client):
    response = client.post("/api/jobs/999999/cancel")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_api_job_012_job_logs_return_page(client):
    from apps.jobs.models import ScanRunLog

    job = create_async_job(kind="scan_job", status="RUNNING")
    target = create_target(host="log-target.testbed.local")
    scan_job = create_scan_job(async_job=job, target_ids=[target.id])
    ScanRunLog.objects.create(
        async_job=job,
        target=target,
        scanner_kind="network",
        status="SUCCESS",
        findings_count=3,
        started_at=timezone.now(),
        finished_at=timezone.now(),
        error=None,
    )

    response = client.get(f"/api/jobs/{job.id}/logs")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert {
        "id",
        "scan_job_id",
        "target_id",
        "target_label",
        "scanner_kind",
        "status",
        "findings_count",
        "started_at",
        "finished_at",
        "error",
    } <= set(item)
    assert item["scan_job_id"] == scan_job.id
    assert item["target_id"] == target.id
    assert item["target_label"] == "log-target.testbed.local:443"


def test_api_job_014_job_logs_exclude_incomplete_internal_rows(client):
    from apps.jobs.models import ScanRunLog

    job = create_async_job(kind="scan_job", status="RUNNING")
    target = create_target(host="complete-log.testbed.local")
    create_scan_job(async_job=job, target_ids=[target.id])
    ScanRunLog.objects.create(
        async_job=job,
        scanner_kind="network",
        status="ERROR",
        findings_count=0,
        error="missing_target",
    )
    ScanRunLog.objects.create(
        async_job=job,
        target=target,
        scanner_kind="network",
        status="SUCCESS",
        findings_count=1,
    )

    response = client.get(f"/api/jobs/{job.id}/logs")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["target_id"] == target.id


def test_api_job_015_job_logs_without_scan_job_returns_empty_page(client):
    from apps.jobs.models import ScanRunLog

    job = create_async_job(kind="scan_job", status="RUNNING")
    target = create_target(host="orphan-log.testbed.local")
    ScanRunLog.objects.create(
        async_job=job,
        target=target,
        scanner_kind="network",
        status="SUCCESS",
        findings_count=1,
    )

    response = client.get(f"/api/jobs/{job.id}/logs")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "offset": 0, "limit": 20}


def test_api_job_013_agent_skip_log_is_visible(client):
    from apps.jobs.models import ScanRunLog

    target = create_target(host="agent-skip.testbed.local")
    job = create_async_job(kind="scan_job", status="COMPLETED")
    create_scan_job(async_job=job, target_ids=[target.id])
    ScanRunLog.objects.create(
        async_job=job,
        target=target,
        scanner_kind="agent.cert_store",
        status="SKIPPED",
        findings_count=0,
        error="agent_stale",
    )

    response = client.get(f"/api/jobs/{job.id}/logs")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["status"] == "SKIPPED"
    assert item["error"] in {"agent_unavailable", "agent_stale", "capability_unsupported"}
