import pytest
from django.utils import timezone

from tests.api.factories import create_target


pytestmark = pytest.mark.django_db


BOOTSTRAP = "test-bootstrap-token"


def register_agent(client, hostname="agent.testbed.local", capabilities=None, expected_status=201):
    response = client.post(
        "/api/agents/register",
        data={
            "hostname": hostname,
            "agent_url": f"http://{hostname}:9100",
            "capabilities": capabilities or ["agent.cert_store"],
            "os_distribution": "ubuntu-22.04",
        },
        content_type="application/json",
        headers={"X-Bootstrap-Token": BOOTSTRAP},
    )
    assert response.status_code == expected_status
    return response


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_api_agt_001_register_agent_returns_token_once(client, settings):
    from apps.agents.models import Agent

    settings.AGENT_BOOTSTRAP_TOKEN = BOOTSTRAP

    response = register_agent(client)

    body = response.json()
    assert body["registration_action"] == "created"
    assert body["agent_token"]
    assert body["token_rotated_at"]
    agent = Agent.objects.get(id=body["id"])
    assert agent.agent_token_hash
    assert agent.agent_token_hash != body["agent_token"]
    assert agent.last_seen is not None
    assert agent.agent_url == "http://agent.testbed.local:9100/"
    assert agent.os_distribution == "ubuntu-22.04"


def test_api_agt_002_existing_hostname_registration_rotates_token(client, settings):
    from apps.agents.models import Agent

    settings.AGENT_BOOTSTRAP_TOKEN = BOOTSTRAP
    first = register_agent(client)
    agent_id = first.json()["id"]
    old_token = first.json()["agent_token"]
    Agent.objects.filter(id=agent_id).update(active=False)

    second = client.post(
        "/api/agents/register",
        data={
            "hostname": "agent.testbed.local",
            "agent_url": "http://agent-new.testbed.local:9200",
            "capabilities": ["agent.cert_store", "agent.ssh_config"],
            "os_distribution": "debian-12",
        },
        content_type="application/json",
        headers={"X-Bootstrap-Token": BOOTSTRAP},
    )
    assert second.status_code == 200

    body = second.json()
    assert body["id"] == agent_id
    assert body["registration_action"] == "token_rotated"
    assert body["agent_token"] != old_token
    assert client.post(f"/api/agents/{agent_id}/heartbeat", headers=bearer(old_token)).status_code == 401
    assert client.post(f"/api/agents/{agent_id}/heartbeat", headers=bearer(body["agent_token"])).status_code == 200
    agent = Agent.objects.get(id=agent_id)
    assert agent.active is True
    assert agent.agent_url == "http://agent-new.testbed.local:9200/"
    assert agent.capabilities == ["agent.cert_store", "agent.ssh_config"]
    assert agent.os_distribution == "debian-12"


def test_api_agt_003_missing_or_invalid_bootstrap_token_is_rejected(client, settings):
    settings.AGENT_BOOTSTRAP_TOKEN = BOOTSTRAP

    response = client.post(
        "/api/agents/register",
        data={"hostname": "agent.testbed.local", "agent_url": "http://agent.testbed.local:9100", "capabilities": []},
        content_type="application/json",
    )

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_token"


def test_api_agt_003b_registration_accepts_missing_agent_url_and_rejects_invalid_url(client, settings):
    from apps.agents.models import Agent

    settings.AGENT_BOOTSTRAP_TOKEN = BOOTSTRAP

    missing_url = client.post(
        "/api/agents/register",
        data={"hostname": "agent-no-url.testbed.local", "capabilities": []},
        content_type="application/json",
        headers={"X-Bootstrap-Token": BOOTSTRAP},
    )
    invalid_url = client.post(
        "/api/agents/register",
        data={"hostname": "agent-bad-url.testbed.local", "agent_url": "not-a-url", "capabilities": []},
        content_type="application/json",
        headers={"X-Bootstrap-Token": BOOTSTRAP},
    )

    assert missing_url.status_code == 201
    assert Agent.objects.get(id=missing_url.json()["id"]).agent_url is None
    assert invalid_url.status_code == 422


def test_api_agt_004_heartbeat_updates_last_seen(client, settings):
    from apps.agents.models import Agent

    settings.AGENT_BOOTSTRAP_TOKEN = BOOTSTRAP
    registered = register_agent(client)
    agent_id = registered.json()["id"]
    token = registered.json()["agent_token"]
    Agent.objects.filter(id=agent_id).update(last_seen=timezone.now() - timezone.timedelta(hours=1))

    response = client.post(f"/api/agents/{agent_id}/heartbeat", headers=bearer(token))

    assert response.status_code == 200
    assert response.json()["received_at"] is not None
    assert Agent.objects.get(id=agent_id).last_seen > timezone.now() - timezone.timedelta(minutes=1)


def test_api_agt_005_inactive_agent_heartbeat_is_rejected(client, settings):
    from apps.agents.models import Agent

    settings.AGENT_BOOTSTRAP_TOKEN = BOOTSTRAP
    registered = register_agent(client)
    agent_id = registered.json()["id"]
    token = registered.json()["agent_token"]
    old_last_seen = timezone.now() - timezone.timedelta(hours=1)
    Agent.objects.filter(id=agent_id).update(active=False, last_seen=old_last_seen)

    response = client.post(f"/api/agents/{agent_id}/heartbeat", headers=bearer(token))

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_token"
    assert Agent.objects.get(id=agent_id).last_seen == old_last_seen


def test_api_agt_006_list_agents_marks_stale_and_hides_tokens(client, settings):
    from apps.agents.models import Agent

    settings.AGENT_BOOTSTRAP_TOKEN = BOOTSTRAP
    fresh = Agent.objects.create(
        hostname="fresh",
        capabilities=[],
        agent_token_hash="hash",
        active=True,
        last_seen=timezone.now(),
    )
    stale = Agent.objects.create(
        hostname="stale",
        capabilities=[],
        agent_token_hash="hash",
        active=True,
        last_seen=timezone.now() - timezone.timedelta(minutes=10),
    )
    inactive = Agent.objects.create(
        hostname="inactive",
        capabilities=[],
        agent_token_hash="hash",
        active=False,
        last_seen=timezone.now(),
    )

    response = client.get("/api/agents")

    assert response.status_code == 200
    by_id = {item["id"]: item for item in response.json()["items"]}
    assert by_id[str(fresh.id)]["is_stale"] is False
    assert by_id[str(fresh.id)]["agent_url"] is None
    assert by_id[str(fresh.id)]["registered_at"] is not None
    assert by_id[str(fresh.id)]["last_seen"] is not None
    assert by_id[str(stale.id)]["is_stale"] is True
    assert by_id[str(inactive.id)]["active"] is False
    assert "agent_token" not in response.content.decode()
    assert "agent_token_hash" not in response.content.decode()


def test_api_agt_010_list_agents_filters_by_active(client, settings):
    from apps.agents.models import Agent

    settings.AGENT_BOOTSTRAP_TOKEN = BOOTSTRAP
    active = Agent.objects.create(
        hostname="active-filter",
        capabilities=[],
        agent_token_hash="hash",
        active=True,
        last_seen=timezone.now(),
    )
    inactive = Agent.objects.create(
        hostname="inactive-filter",
        capabilities=[],
        agent_token_hash="hash",
        active=False,
        last_seen=timezone.now(),
    )

    active_response = client.get("/api/agents?active=true")
    inactive_response = client.get("/api/agents?active=false")

    assert active_response.status_code == 200
    assert {item["id"] for item in active_response.json()["items"]} == {str(active.id)}
    assert inactive_response.status_code == 200
    assert {item["id"] for item in inactive_response.json()["items"]} == {str(inactive.id)}


def test_api_agt_007_agent_detail_hides_tokens(client, settings):
    from apps.agents.models import Agent

    settings.AGENT_BOOTSTRAP_TOKEN = BOOTSTRAP
    agent = Agent.objects.create(
        hostname="detail",
        capabilities=["agent.cert_store"],
        agent_token_hash="hash",
        active=True,
        last_seen=timezone.now(),
    )

    response = client.get(f"/api/agents/{agent.id}")

    assert response.status_code == 200
    body = response.json()
    assert {
        "agent_url",
        "os_distribution",
        "registered_at",
        "token_rotated_at",
        "last_seen",
        "active",
        "is_stale",
    } <= set(body)
    assert "agent_token" not in body
    assert "agent_token_hash" not in body


def test_api_agt_008_delete_agent_soft_deactivates(client, settings):
    from apps.agents.models import Agent

    settings.AGENT_BOOTSTRAP_TOKEN = BOOTSTRAP
    registered = register_agent(client)
    agent_id = registered.json()["id"]

    response = client.delete(f"/api/agents/{agent_id}")

    assert response.status_code == 204
    agent = Agent.objects.get(id=agent_id)
    assert agent.active is False


def test_api_agt_009_worker_skips_stale_or_capability_mismatch_agent():
    from apps.agents.models import Agent
    from apps.agents.services import record_agent_scanner_skip_if_needed
    from apps.jobs.models import ScanRunLog
    from tests.api.factories import create_async_job

    target = create_target(agent_enabled=True, host="agent.testbed.local")
    job = create_async_job(kind="scan_job", status="RUNNING")
    Agent.objects.create(
        hostname=target.host,
        capabilities=["agent.cert_store"],
        agent_token_hash="hash",
        active=True,
        last_seen=timezone.now() - timezone.timedelta(minutes=10),
    )

    skipped = record_agent_scanner_skip_if_needed(job, target, "agent.ssh_config")

    assert skipped is True
    log = ScanRunLog.objects.get(async_job=job)
    assert log.status == "SKIPPED"
    assert log.error in {"agent_stale", "capability_unsupported"}
