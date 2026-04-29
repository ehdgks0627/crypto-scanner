import pytest
from django.utils import timezone

from tests.api.factories import assert_job_envelope


pytestmark = pytest.mark.django_db


def create_discovery(**overrides):
    from apps.discoveries.models import Discovery
    from tests.api.factories import create_async_job

    async_job = overrides.pop("async_job", None) or create_async_job(kind="discovery")
    values = {
        "async_job": async_job,
        "cidr": "10.0.0.0/24",
        "status": async_job.status,
        "started_at": async_job.started_at,
    }
    values.update(overrides)
    return Discovery.objects.create(**values)


def test_api_dsc_001_list_discoveries_returns_page(client):
    create_discovery(status="COMPLETED")
    create_discovery(status="RUNNING")

    response = client.get("/api/discoveries?status=COMPLETED&limit=20&offset=0")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "COMPLETED"


def test_api_dsc_002_create_discovery_returns_job_envelope(client):
    response = client.post(
        "/api/discoveries",
        data={"cidr": "10.0.0.0/24", "ports": [443], "include_default_ports": True},
        content_type="application/json",
    )

    assert response.status_code == 202
    body = response.json()
    assert_job_envelope(body)
    assert body["kind"] == "discovery"
    assert body["resource"]["kind"] == "discovery"
    assert body["status"] == "PENDING"
    assert body["progress"] is None
    assert body["result"] is None


def test_api_dsc_003_detail_separates_created_and_started_at(client):
    pending = create_discovery(status="PENDING", started_at=None)
    running = create_discovery(status="RUNNING", started_at=timezone.now())

    pending_response = client.get(f"/api/discoveries/{pending.id}")
    running_response = client.get(f"/api/discoveries/{running.id}")

    assert pending_response.status_code == 200
    assert pending_response.headers["Cache-Control"] == "no-store"
    assert pending_response.json()["created_at"] is not None
    assert pending_response.json()["started_at"] is None
    assert running_response.json()["started_at"] is not None


def test_api_dsc_004_endpoint_list_separates_detected_and_suggested_protocol(client):
    from apps.discoveries.models import DiscoveredEndpoint

    discovery = create_discovery(status="COMPLETED")
    for host, detected, suggested in [
        ("web.testbed.local", "HTTPS", "TLS"),
        ("ssh.testbed.local", "SSH", "SSH"),
        ("db.testbed.local", "PostgreSQL", "UNKNOWN"),
    ]:
        DiscoveredEndpoint.objects.create(
            discovery=discovery,
            host=host,
            port=443,
            transport="TCP",
            detected_protocol=detected,
            suggested_protocol_hint=suggested,
        )

    response = client.get(f"/api/discoveries/{discovery.id}/endpoints")

    assert response.status_code == 200
    protocols = {(item["detected_protocol"], item["suggested_protocol_hint"]) for item in response.json()["items"]}
    assert {("HTTPS", "TLS"), ("SSH", "SSH"), ("PostgreSQL", "UNKNOWN")} <= protocols


def test_api_dsc_005_promote_endpoints_creates_targets(client):
    from apps.discoveries.models import DiscoveredEndpoint
    from apps.targets.models import Target

    discovery = create_discovery(status="COMPLETED")
    endpoint_a = DiscoveredEndpoint.objects.create(
        discovery=discovery,
        host="web.testbed.local",
        port=443,
        transport="TCP",
        detected_protocol="HTTPS",
        suggested_protocol_hint="TLS",
    )
    endpoint_b = DiscoveredEndpoint.objects.create(
        discovery=discovery,
        host="ssh.testbed.local",
        port=22,
        transport="TCP",
        detected_protocol="SSH",
        suggested_protocol_hint="SSH",
    )

    response = client.post(
        f"/api/discoveries/{discovery.id}/promote",
        data={"endpoint_ids": [endpoint_a.id, endpoint_b.id], "target_overrides": {"context": {"criticality": "high"}}},
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response.json()
    assert len(body["promotions"]) == 2
    assert Target.objects.count() == 2
    endpoint_a.refresh_from_db()
    endpoint_b.refresh_from_db()
    assert endpoint_a.promoted is True
    assert endpoint_a.target_id is not None
    assert endpoint_b.promoted is True
    assert endpoint_b.target_id is not None


def test_api_dsc_006_enqueue_failure_returns_503_without_orphans(client, monkeypatch):
    from apps.discoveries import services
    from apps.discoveries.models import Discovery
    from apps.jobs.models import AsyncJob

    def fail_enqueue(discovery):
        raise services.EnqueueUnavailable("queue unavailable")

    monkeypatch.setattr(services, "enqueue_discovery", fail_enqueue)

    response = client.post(
        "/api/discoveries",
        data={"cidr": "10.0.0.0/24"},
        content_type="application/json",
    )

    assert response.status_code == 503
    assert response.json()["error"] == "service_unavailable"
    assert Discovery.objects.count() == 0
    assert AsyncJob.objects.count() == 0


def test_api_dsc_007_cancelled_discovery_preserves_partial_endpoints(client):
    from apps.discoveries.models import DiscoveredEndpoint

    discovery = create_discovery(status="CANCELLED")
    DiscoveredEndpoint.objects.create(
        discovery=discovery,
        host="web.testbed.local",
        port=443,
        detected_protocol="HTTPS",
        suggested_protocol_hint="TLS",
    )
    DiscoveredEndpoint.objects.create(
        discovery=discovery,
        host="ssh.testbed.local",
        port=22,
        detected_protocol="SSH",
        suggested_protocol_hint="SSH",
    )

    detail_response = client.get(f"/api/discoveries/{discovery.id}")
    endpoints_response = client.get(f"/api/discoveries/{discovery.id}/endpoints")
    promote_response = client.post(
        f"/api/discoveries/{discovery.id}/promote",
        data={"endpoint_ids": []},
        content_type="application/json",
    )

    assert detail_response.json()["status"] == "CANCELLED"
    assert endpoints_response.status_code == 200
    assert endpoints_response.json()["total"] == 2
    assert promote_response.status_code == 409
    assert promote_response.json()["error"] == "conflict"
