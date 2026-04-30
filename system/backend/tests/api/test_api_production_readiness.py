import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.api.factories import create_asset, create_snapshot, create_target


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


def test_pr_auth_002_production_requires_api_and_non_default_bootstrap_tokens():
    backend_dir = Path(__file__).resolve().parents[2]
    env = {
        **os.environ,
        "DJANGO_DEBUG": "false",
        "DJANGO_SECRET_KEY": "production-secret",
        "API_AUTH_TOKEN": "",
        "AGENT_BOOTSTRAP_TOKEN": "dev-bootstrap-token",
    }

    result = subprocess.run(
        [sys.executable, "-c", "import pqc_ras.settings"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "API_AUTH_TOKEN must be set" in result.stderr


def test_pr_auth_003_production_requires_allowed_hosts():
    backend_dir = Path(__file__).resolve().parents[2]
    env = {
        **os.environ,
        "DJANGO_DEBUG": "false",
        "DJANGO_SECRET_KEY": "production-secret",
        "API_AUTH_TOKEN": "api-token",
        "AGENT_BOOTSTRAP_TOKEN": "bootstrap-token",
        "DJANGO_ALLOWED_HOSTS": "",
    }

    result = subprocess.run(
        [sys.executable, "-c", "import pqc_ras.settings"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "DJANGO_ALLOWED_HOSTS must be set" in result.stderr


def test_pr_auth_004_allowed_hosts_is_enforced_at_request_time(client, settings):
    settings.ALLOWED_HOSTS = ["good.test"]

    blocked = client.get("/api/health", HTTP_HOST="evil.test")
    allowed = client.get("/api/health", HTTP_HOST="good.test")

    assert blocked.status_code == 400
    assert allowed.status_code == 200


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
        data={
            "hostname": "agent-hash.testbed.local",
            "agent_url": "http://agent-hash.testbed.local:9100",
            "capabilities": ["agent.cert_store"],
        },
        content_type="application/json",
        headers={"X-Bootstrap-Token": "bootstrap"},
    )

    assert response.status_code == 201
    token = response.json()["agent_token"]
    agent = Agent.objects.get(id=response.json()["id"])
    assert agent.agent_token_hash != token
    assert agent.agent_token_hash.startswith(("pbkdf2_", "argon2", "bcrypt"))
    assert client.post(f"/api/agents/{agent.id}/heartbeat", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_pr_db_002_duplicate_target_endpoint_is_rejected():
    from django.db import IntegrityError

    create_target(host="unique.testbed.local", port=443, transport="TCP")
    with pytest.raises(IntegrityError):
        create_target(host="unique.testbed.local", port=443, transport="TCP")


def test_pr_db_003_duplicate_asset_bom_ref_is_rejected_per_snapshot():
    from django.db import IntegrityError
    from django.db import transaction

    snapshot = create_snapshot()
    create_asset(snapshot=snapshot, bom_ref="cert:unique")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create_asset(snapshot=snapshot, bom_ref="cert:unique")

    other_snapshot = create_snapshot(serial_number="urn:uuid:other")
    assert create_asset(snapshot=other_snapshot, bom_ref="cert:unique").id


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
