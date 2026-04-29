import pytest
from django.utils import timezone

from tests.api.factories import assert_job_envelope, create_async_job, create_target


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
    assert ScanJob.objects.count() == 0


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
def test_api_job_007_running_scan_and_discovery_cancel_sets_requested_at(client, kind):
    job = create_async_job(kind=kind, status="RUNNING")

    response = client.post(f"/api/jobs/{job.id}/cancel")

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "RUNNING"
    assert body["cancel_requested_at"] is not None
    job.refresh_from_db()
    assert job.status == "RUNNING"
    assert job.cancel_requested_at is not None


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


@pytest.mark.parametrize("status", ["COMPLETED", "FAILED", "CANCELLED"])
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
    ScanRunLog.objects.create(
        async_job=job,
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
    assert {"scanner_kind", "status", "findings_count", "started_at", "finished_at", "error"} <= set(item)


def test_api_job_013_agent_skip_log_is_visible(client):
    from apps.jobs.models import ScanRunLog

    job = create_async_job(kind="scan_job", status="COMPLETED")
    ScanRunLog.objects.create(
        async_job=job,
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
