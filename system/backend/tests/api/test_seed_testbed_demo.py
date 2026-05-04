import pytest
from django.core.management import call_command

from apps.agents.models import Agent
from apps.discoveries.models import Discovery
from apps.risk.models import RiskScore
from apps.snapshots.models import CbomSnapshot
from apps.targets.models import Target


pytestmark = pytest.mark.django_db


def test_seed_testbed_demo_populates_dashboard_scenario(client):
    call_command("seed_testbed_demo", "--reset")

    latest = CbomSnapshot.objects.order_by("-id").first()
    assert latest.serial_number == "testbed-demo-latest"
    assert latest.assets.count() == 21
    assert RiskScore.objects.filter(snapshot=latest, tier="CRITICAL").count() == 4
    assert Target.objects.count() == 31
    discovery = Discovery.objects.get(cidr="172.20.0.0/16")
    assert discovery.endpoints.count() == 33
    assert discovery.discovery_agent.agent_role == Agent.ROLE_DISCOVERY

    response = client.get("/api/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["snapshot"]["id"] == latest.id
    assert body["snapshot"]["asset_count"] == 21
    assert body["by_tier"]["CRITICAL"] == 4
    assert body["by_tier"]["HIGH"] == 11
    assert body["quantum_vulnerable_ratio"]["vulnerable"] == 17
    assert body["agents_status"]["total"] == 11
    assert len(body["recent_jobs"]) == 5
    assert {job["status"] for job in body["recent_jobs"]} >= {"COMPLETED", "FAILED", "CANCELLED"}
