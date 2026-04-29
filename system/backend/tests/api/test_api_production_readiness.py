import pytest

from tests.api.factories import create_target


pytestmark = pytest.mark.django_db


def test_pr_auth_001_optional_api_token_middleware_protects_non_exempt_endpoints(client, settings):
    settings.API_AUTH_TOKEN = "prod-secret"

    blocked = client.get("/api/targets")
    allowed = client.get("/api/targets", headers={"X-API-Token": "prod-secret"})
    health = client.get("/api/health")

    assert blocked.status_code == 401
    assert blocked.json()["error"] == "invalid_token"
    assert blocked.headers["X-Request-Id"]
    assert allowed.status_code == 200
    assert health.status_code == 200


def test_pr_val_001_mutation_payloads_reject_unknown_fields(client):
    response = client.post(
        "/api/targets",
        data={"host": "strict.testbed.local", "port": 443, "protocol_hint": "TLS", "unexpected": "nope"},
        content_type="application/json",
    )

    assert response.status_code == 422
    assert response.json()["error"] == "unprocessable"


def test_pr_agt_001_agent_token_uses_password_hasher(client, settings):
    from apps.agents.models import Agent

    settings.AGENT_BOOTSTRAP_TOKEN = "bootstrap"

    response = client.post(
        "/api/agents/register",
        data={"hostname": "agent-hash.testbed.local", "capabilities": ["agent.cert_store"]},
        content_type="application/json",
        headers={"X-Bootstrap-Token": "bootstrap"},
    )

    assert response.status_code == 201
    token = response.json()["agent_token"]
    agent = Agent.objects.get(id=response.json()["id"])
    assert agent.agent_token_hash != token
    assert agent.agent_token_hash.startswith(("pbkdf2_", "argon2", "bcrypt"))
    assert client.post(f"/api/agents/{agent.id}/heartbeat", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_pr_db_002_duplicate_target_natural_key_is_rejected():
    from django.db import IntegrityError

    create_target(host="unique.testbed.local", port=443, transport="TCP")
    with pytest.raises(IntegrityError):
        create_target(host="unique.testbed.local", port=443, transport="TCP")


def test_pr_job_004_scan_job_enqueue_creates_durable_task(client):
    from apps.jobs.models import QueuedTask

    target = create_target(host="queue.testbed.local")

    response = client.post(
        "/api/jobs",
        data={"target_ids": [target.id], "scanners": ["network"]},
        content_type="application/json",
    )

    assert response.status_code == 202
    queued_task = QueuedTask.objects.get(async_job_id=response.json()["id"])
    assert queued_task.task_name == "scan_job"
    assert queued_task.status == "QUEUED"
    assert queued_task.payload["target_ids"] == [target.id]


def test_pr_ops_003_json_log_formatter_includes_operational_fields():
    import json
    import logging

    from apps.core.logging import JsonFormatter

    record = logging.LogRecord(
        name="apps.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="job started",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-1"
    record.job_id = 42

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["message"] == "job started"
    assert payload["request_id"] == "req-1"
    assert payload["job_id"] == 42
