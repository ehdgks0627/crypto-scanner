import pytest
from django.utils import timezone

from tests.api.factories import (
    assert_job_envelope,
    create_asset,
    create_async_job,
    create_risk_score,
    create_snapshot,
)


pytestmark = pytest.mark.django_db


def test_api_dsh_001_dashboard_summary_uses_latest_snapshot(client):
    from apps.agents.models import Agent

    older = create_snapshot(serial_number="older")
    latest = create_snapshot(serial_number="latest")
    old_asset = create_asset(snapshot=older, bom_ref="old")
    latest_asset = create_asset(snapshot=latest, bom_ref="latest", asset_type="certificate")
    create_risk_score(old_asset, score=20.0, tier="LOW")
    create_risk_score(latest_asset, score=95.0, tier="CRITICAL")
    job = create_async_job(kind="scan_job", status="COMPLETED", result={"snapshot_id": latest.id})
    Agent.objects.create(
        hostname="agent",
        capabilities=[],
        agent_token_hash="hash",
        active=True,
        last_seen=timezone.now(),
    )

    response = client.get("/api/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["snapshot"]["id"] == latest.id
    assert body["snapshot"]["created_at"] is not None
    assert body["snapshot"]["asset_count"] == 1
    assert body["kpis"]["discovered_crypto_assets_per_scan"] == {
        "value": 1,
        "unit": "assets",
        "source": "cbom_snapshot",
        "snapshot_id": latest.id,
        "scan_job_id": None,
    }
    assert body["by_tier"]["CRITICAL"] == 1
    assert body["by_asset_type"]["certificate"] == 1
    assert body["by_algorithm_family"]["RSA"] == 1
    assert body["quantum_vulnerable_ratio"]["vulnerable"] == 1
    assert body["quantum_vulnerable_ratio"]["safe"] == 0
    assert body["agents_status"] == {"total": 1, "active": 1, "stale": 0}
    assert body["recent_jobs"][0]["id"] == job.id
    assert_job_envelope(body["recent_jobs"][0])
    assert isinstance(body["trend"], list)


def test_api_dsh_002_dashboard_empty_state_without_snapshots(client):
    response = client.get("/api/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["snapshot"] is None
    assert body["by_tier"] == {}
    assert body["by_asset_type"] == {}
    assert body["by_algorithm_family"] == {}
    assert body["quantum_vulnerable_ratio"] == {"vulnerable": 0, "safe": 0, "unknown": 0}
    assert body["kpis"]["discovered_crypto_assets_per_scan"]["value"] == 0
    assert body["recent_jobs"] == []
    assert body["trend"] == []


def test_api_dsh_003_dashboard_does_not_expose_agent_tokens(client):
    from apps.agents.models import Agent

    Agent.objects.create(
        hostname="agent",
        capabilities=[],
        agent_token_hash="super-secret-hash",
        active=True,
        last_seen=timezone.now(),
    )

    response = client.get("/api/dashboard/summary")

    assert response.status_code == 200
    content = response.content.decode()
    assert "agent_token" not in content
    assert "agent_token_hash" not in content
    assert "super-secret-hash" not in content
    assert {"total", "active", "stale"} <= set(response.json()["agents_status"])
