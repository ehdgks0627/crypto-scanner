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
        "scope_type": "cidr",
        "scope_value": "10.0.0.0/24",
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


def test_api_dsc_002b_create_discovery_defaults_default_ports_to_true(client):
    from apps.discoveries.models import Discovery

    response = client.post(
        "/api/discoveries",
        data={"cidr": "10.0.1.0/24"},
        content_type="application/json",
    )

    assert response.status_code == 202
    discovery = Discovery.objects.get(id=response.json()["resource"]["id"])
    assert discovery.include_default_ports is True
    assert discovery.ports == []
    assert discovery.scope_type == "cidr"
    assert discovery.scope_value == "10.0.1.0/24"


def test_api_dsc_002c_create_discovery_rejects_invalid_ports_and_status_filter(client):
    invalid_ports = client.post(
        "/api/discoveries",
        data={"cidr": "10.0.2.0/24", "ports": [0, 65536]},
        content_type="application/json",
    )
    invalid_status = client.get("/api/discoveries?status=NOPE")

    assert invalid_ports.status_code == 422
    assert invalid_ports.json()["error"] == "unprocessable"
    assert invalid_status.status_code == 422


def test_api_dsc_002d_create_discovery_accepts_ip_and_domain_scopes(client):
    from apps.discoveries.models import Discovery
    from apps.jobs.models import QueuedTask

    ip_response = client.post(
        "/api/discoveries",
        data={"scope_type": "ip", "scope_value": "10.0.1.8", "ports": [443]},
        content_type="application/json",
    )
    domain_response = client.post(
        "/api/discoveries",
        data={"scope_type": "domain", "scope_value": "App.Testbed.Local", "ports": [443]},
        content_type="application/json",
    )

    assert ip_response.status_code == 202
    assert domain_response.status_code == 202

    ip_discovery = Discovery.objects.get(id=ip_response.json()["resource"]["id"])
    domain_discovery = Discovery.objects.get(id=domain_response.json()["resource"]["id"])
    assert ip_discovery.scope_type == "ip"
    assert ip_discovery.scope_value == "10.0.1.8"
    assert ip_discovery.cidr == "10.0.1.8"
    assert domain_discovery.scope_type == "domain"
    assert domain_discovery.scope_value == "app.testbed.local"
    assert domain_discovery.cidr == "app.testbed.local"

    ip_task = QueuedTask.objects.get(async_job=ip_discovery.async_job)
    assert ip_task.payload["scope_type"] == "ip"
    assert ip_task.payload["scope_value"] == "10.0.1.8"
    assert ip_task.payload["executor_type"] == "central"
    assert ip_task.payload["agent_id"] is None


def test_api_dsc_002e_create_discovery_can_run_on_discovery_agent(client):
    from apps.agents.models import Agent
    from apps.discoveries.models import Discovery
    from apps.jobs.models import QueuedTask

    agent = Agent.objects.create(
        hostname="probe.dmz.testbed.local",
        agent_role="discovery",
        agent_url="http://probe.dmz.testbed.local:9100",
        capabilities=["agent.discovery"],
        agent_token_hash="hash",
        agent_runtime_token="runtime-token",
        active=True,
        last_seen=timezone.now(),
    )

    response = client.post(
        "/api/discoveries",
        data={
            "scope_type": "cidr",
            "scope_value": "10.0.3.0/24",
            "executor_type": "agent",
            "agent_id": str(agent.id),
            "ports": [443],
        },
        content_type="application/json",
    )

    assert response.status_code == 202
    discovery = Discovery.objects.get(id=response.json()["resource"]["id"])
    assert discovery.executor_type == "agent"
    assert discovery.discovery_agent_id == agent.id
    task = QueuedTask.objects.get(async_job=discovery.async_job)
    assert task.payload["executor_type"] == "agent"
    assert task.payload["agent_id"] == str(agent.id)

    detail_response = client.get(f"/api/discoveries/{discovery.id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["agent_hostname"] == "probe.dmz.testbed.local"


def test_api_dsc_002e_worker_calls_discovery_agent_and_persists_endpoints(client, monkeypatch):
    from apps.agents.models import Agent
    from apps.discoveries import services
    from apps.discoveries.models import DiscoveredEndpoint, Discovery
    from apps.jobs.models import AsyncJob, QueuedTask

    agent = Agent.objects.create(
        hostname="probe.dmz.testbed.local",
        agent_role="discovery",
        agent_url="http://probe.dmz.testbed.local:9100",
        capabilities=["agent.discovery"],
        agent_token_hash="hash",
        agent_runtime_token="runtime-token",
        active=True,
        last_seen=timezone.now(),
    )
    response = client.post(
        "/api/discoveries",
        data={
            "scope_type": "cidr",
            "scope_value": "172.31.240.0/24",
            "executor_type": "agent",
            "agent_id": str(agent.id),
            "ports": [443, 22],
            "include_default_ports": False,
        },
        content_type="application/json",
    )
    discovery = Discovery.objects.get(id=response.json()["resource"]["id"])
    task = QueuedTask.objects.get(async_job=discovery.async_job)
    agent_requests = []

    def fake_post_discover(agent_arg, payload):
        agent_requests.append((agent_arg.id, payload))
        return {
            "endpoints": [
                {
                    "host": "172.31.240.10",
                    "port": 443,
                    "transport": "TCP",
                    "detected_protocol": "TLS",
                    "suggested_protocol_hint": "TLS",
                    "availability_metrics": {
                        "measurement_type": "tls_availability_check",
                        "sample_count": 3,
                        "successful_handshakes": 3,
                        "tcp_connect_ms": {"p50": 2.0, "p95": 3.0, "samples": 3},
                        "handshake_ms": {"p50": 12.0, "p95": 15.0, "samples": 3},
                        "failure_rate": 0.0,
                        "timeout_rate": 0.0,
                        "handshake_bytes_sent": 1800,
                        "handshake_bytes_received": 3200,
                    },
                },
                {"host": "172.31.240.12", "port": 22, "transport": "TCP", "detected_protocol": "SSH", "suggested_protocol_hint": "SSH"},
            ],
            "availability_report": {
                "measured_endpoint_count": 1,
                "tls_endpoint_count": 1,
                "sample_count": 3,
                "averages": {"handshake_p95_ms": 15.0},
            },
        }

    monkeypatch.setattr(services.agent_client, "post_discover", fake_post_discover)

    result = services.process_discovery_task(task.id)

    assert result == {
        "discovery_id": discovery.id,
        "executor_type": "agent",
        "endpoints_count": 2,
        "availability_report": {
            "measured_endpoint_count": 1,
            "tls_endpoint_count": 1,
            "sample_count": 3,
            "averages": {"handshake_p95_ms": 15.0},
        },
    }
    assert agent_requests == [
        (
            agent.id,
            {
                "scope_type": "cidr",
                "scope_value": "172.31.240.0/24",
                "cidr": "172.31.240.0/24",
                "ports": [22, 443],
            },
        )
    ]
    assert {(endpoint.host, endpoint.port, endpoint.detected_protocol) for endpoint in DiscoveredEndpoint.objects.filter(discovery=discovery)} == {
        ("172.31.240.10", 443, "TLS"),
        ("172.31.240.12", 22, "SSH"),
    }
    tls_endpoint = DiscoveredEndpoint.objects.get(discovery=discovery, port=443)
    assert tls_endpoint.availability_metrics["handshake_ms"]["p95"] == 15.0
    endpoint_response = client.get(f"/api/discoveries/{discovery.id}/endpoints")
    assert endpoint_response.json()["items"][0]["availability_metrics"]["measurement_type"] == "tls_availability_check"
    task.refresh_from_db()
    discovery.refresh_from_db()
    discovery.async_job.refresh_from_db()
    assert task.status == QueuedTask.COMPLETED
    assert discovery.status == AsyncJob.COMPLETED
    assert discovery.async_job.progress == {"current": 2, "total": 2, "percent": 100}
    assert discovery.async_job.result["availability_report"]["sample_count"] == 3
    detail_response = client.get(f"/api/discoveries/{discovery.id}")
    assert detail_response.json()["availability_report"]["measured_endpoint_count"] == 1


def test_api_dsc_002f_create_discovery_rejects_invalid_scope_values(client):
    invalid_ip = client.post(
        "/api/discoveries",
        data={"scope_type": "ip", "scope_value": "not-an-ip", "ports": [443]},
        content_type="application/json",
    )
    invalid_cidr = client.post(
        "/api/discoveries",
        data={"scope_type": "cidr", "scope_value": "10.0.0.1", "ports": [443]},
        content_type="application/json",
    )
    invalid_domain = client.post(
        "/api/discoveries",
        data={"scope_type": "domain", "scope_value": "bad/domain", "ports": [443]},
        content_type="application/json",
    )

    assert invalid_ip.status_code == 422
    assert invalid_cidr.status_code == 422
    assert invalid_domain.status_code == 422


def test_api_dsc_002g_create_discovery_rejects_unusable_discovery_agent(client):
    from apps.agents.models import Agent

    host_agent = Agent.objects.create(
        hostname="host-only.testbed.local",
        agent_role="host",
        capabilities=["agent.cert_store"],
        agent_token_hash="hash",
        active=True,
        last_seen=timezone.now(),
    )
    stale_discovery_agent = Agent.objects.create(
        hostname="stale-probe.testbed.local",
        agent_role="discovery",
        capabilities=["agent.discovery"],
        agent_token_hash="hash",
        active=True,
        last_seen=timezone.now() - timezone.timedelta(minutes=10),
    )

    missing_agent = client.post(
        "/api/discoveries",
        data={
            "scope_type": "cidr",
            "scope_value": "10.0.4.0/24",
            "executor_type": "agent",
            "ports": [443],
        },
        content_type="application/json",
    )
    host_agent_response = client.post(
        "/api/discoveries",
        data={
            "scope_type": "cidr",
            "scope_value": "10.0.4.0/24",
            "executor_type": "agent",
            "agent_id": str(host_agent.id),
            "ports": [443],
        },
        content_type="application/json",
    )
    stale_agent_response = client.post(
        "/api/discoveries",
        data={
            "scope_type": "cidr",
            "scope_value": "10.0.4.0/24",
            "executor_type": "agent",
            "agent_id": str(stale_discovery_agent.id),
            "ports": [443],
        },
        content_type="application/json",
    )

    assert missing_agent.status_code == 422
    assert host_agent_response.status_code == 422
    assert host_agent_response.json()["error"] == "agent_unavailable"
    assert stale_agent_response.status_code == 409
    assert stale_agent_response.json()["error"] == "agent_unavailable"


def test_api_dsc_003_detail_separates_created_and_started_at(client):
    pending = create_discovery(status="PENDING", started_at=None)
    running = create_discovery(status="RUNNING", started_at=timezone.now())

    pending_response = client.get(f"/api/discoveries/{pending.id}")
    running_response = client.get(f"/api/discoveries/{running.id}")

    assert pending_response.status_code == 200
    assert pending_response.headers["Cache-Control"] == "no-store"
    assert pending_response.json()["created_at"] is not None
    assert pending_response.json()["scope_type"] == "cidr"
    assert pending_response.json()["scope_value"] == "10.0.0.0/24"
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
        data={
            "promotions": [
                {
                    "endpoint_id": endpoint_a.id,
                    "host": "web.testbed.local",
                    "protocol_hint": "TLS",
                    "context": {"criticality": "high"},
                },
                {
                    "endpoint_id": endpoint_b.id,
                    "host": "ssh.testbed.local",
                    "protocol_hint": "SSH",
                    "context": {"criticality": "high"},
                },
            ]
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response.json()
    assert len(body["promoted"]) == 2
    assert body["skipped"] == []
    assert Target.objects.count() == 2
    endpoint_a.refresh_from_db()
    endpoint_b.refresh_from_db()
    assert endpoint_a.promoted is True
    assert endpoint_a.target_id is not None
    assert endpoint_b.promoted is True
    assert endpoint_b.target_id is not None


def test_api_dsc_008_promote_applies_per_promotion_target_fields(client):
    from apps.discoveries.models import DiscoveredEndpoint
    from apps.targets.models import Target

    discovery = create_discovery(status="COMPLETED")
    endpoint = DiscoveredEndpoint.objects.create(
        discovery=discovery,
        host="10.0.0.8",
        port=443,
        transport="TCP",
        detected_protocol="HTTPS",
        suggested_protocol_hint="TLS",
    )

    response = client.post(
        f"/api/discoveries/{discovery.id}/promote",
        data={
            "promotions": [
                {
                    "endpoint_id": endpoint.id,
                    "host": "app.testbed.local",
                    "protocol_hint": "TLS",
                    "agent_enabled": True,
                    "context": {"criticality": "critical", "service_role": "edge-api"},
                }
            ]
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    target = Target.objects.get(id=response.json()["promoted"][0]["target_id"])
    assert target.host == "app.testbed.local"
    assert target.protocol_hint == "TLS"
    assert target.agent_enabled is True
    assert target.context["criticality"] == "critical"
    assert target.context["service_role"] == "edge-api"


def test_api_dsc_009_promote_skips_missing_and_already_promoted_endpoints(client):
    from apps.discoveries.models import DiscoveredEndpoint
    from tests.api.factories import create_target

    discovery = create_discovery(status="COMPLETED")
    target = create_target(host="existing.testbed.local")
    endpoint = DiscoveredEndpoint.objects.create(
        discovery=discovery,
        host="existing.testbed.local",
        port=443,
        transport="TCP",
        detected_protocol="HTTPS",
        suggested_protocol_hint="TLS",
        promoted=True,
        target=target,
    )

    response = client.post(
        f"/api/discoveries/{discovery.id}/promote",
        data={
            "promotions": [
                {"endpoint_id": endpoint.id, "host": "existing.testbed.local", "protocol_hint": "TLS"},
                {"endpoint_id": 999999, "host": "missing.testbed.local", "protocol_hint": "TLS"},
            ]
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["promoted"] == []
    assert response.json()["skipped"] == [
        {"endpoint_id": endpoint.id, "reason": "already_promoted"},
        {"endpoint_id": 999999, "reason": "endpoint_not_found"},
    ]


def test_api_dsc_010_promote_rejects_invalid_protocol_and_context(client):
    from apps.discoveries.models import DiscoveredEndpoint

    discovery = create_discovery(status="COMPLETED")
    endpoint = DiscoveredEndpoint.objects.create(
        discovery=discovery,
        host="web.testbed.local",
        port=443,
        transport="TCP",
        detected_protocol="HTTPS",
        suggested_protocol_hint="TLS",
    )

    response = client.post(
        f"/api/discoveries/{discovery.id}/promote",
        data={
            "promotions": [
                {
                    "endpoint_id": endpoint.id,
                    "host": "web.testbed.local",
                    "protocol_hint": "HTTP",
                    "context": {"exposure": "internet"},
                }
            ]
        },
        content_type="application/json",
    )

    assert response.status_code == 422


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
        data={"promotions": [{"endpoint_id": 1, "host": "web.testbed.local", "protocol_hint": "TLS"}]},
        content_type="application/json",
    )

    assert detail_response.json()["status"] == "CANCELLED"
    assert endpoints_response.status_code == 200
    assert endpoints_response.json()["total"] == 2
    assert promote_response.status_code == 409
    assert promote_response.json()["error"] == "conflict"
