import pytest
from django.core.management import call_command

from apps.agents.models import Agent
from apps.core.management.commands.seed_testbed_demo import DORMANT_PRIVATE_KEY_PATHS, EXPIRING_CERTIFICATE_DAYS, LATEST_ASSETS
from apps.discoveries.models import Discovery
from apps.risk.models import RiskScore
from apps.snapshots.models import CbomSnapshot
from apps.targets.models import Target


pytestmark = pytest.mark.django_db

VULNERABLE_ALGORITHM_FAMILIES = {"RSA", "ECDSA", "ECDH", "DH"}


def test_seed_testbed_demo_populates_dashboard_scenario(client):
    call_command("seed_testbed_demo", "--reset")

    latest = CbomSnapshot.objects.order_by("-id").first()
    assert latest.serial_number == "testbed-demo-latest"
    assert latest.assets.count() == len(LATEST_ASSETS)
    assert latest.assets.values("target").distinct().count() == Target.objects.count()
    assert RiskScore.objects.filter(snapshot=latest, tier="CRITICAL").count() == 18
    assert Target.objects.count() == 31
    discovery = Discovery.objects.get(cidr="172.20.0.0/16")
    assert discovery.endpoints.count() == 33
    assert discovery.discovery_agent.agent_role == Agent.ROLE_DISCOVERY

    response = client.get("/api/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["snapshot"]["id"] == latest.id
    assert body["snapshot"]["asset_count"] == len(LATEST_ASSETS)
    assert body["kpis"]["discovered_crypto_assets_per_scan"]["value"] == len(LATEST_ASSETS)
    assert body["kpis"]["discovered_crypto_assets_per_scan"]["scan_job_id"] == latest.scan_job_id
    assert body["kpis"]["quantum_vulnerable_assets_per_scan"]["value"] == len(
        [asset for asset in LATEST_ASSETS if asset.algorithm_family in VULNERABLE_ALGORITHM_FAMILIES]
    )
    assert body["kpis"]["quantum_vulnerable_assets_per_scan"]["scan_job_id"] == latest.scan_job_id
    assert body["kpis"]["expiring_certificates_90d_per_scan"]["value"] == len(EXPIRING_CERTIFICATE_DAYS)
    assert body["kpis"]["expiring_certificates_90d_per_scan"]["scan_job_id"] == latest.scan_job_id
    assert body["kpis"]["dormant_private_keys_per_scan"]["value"] == len(DORMANT_PRIVATE_KEY_PATHS)
    assert body["kpis"]["dormant_private_keys_per_scan"]["scan_job_id"] == latest.scan_job_id
    assert body["kpis"]["automated_inventory_runtime_minutes_per_scan"]["value"] == 6
    assert body["kpis"]["automated_inventory_runtime_minutes_per_scan"]["scan_job_id"] == latest.scan_job_id
    assert body["by_tier"]["CRITICAL"] == 18
    assert body["by_tier"]["HIGH"] == 31
    assert body["quantum_vulnerable_ratio"]["vulnerable"] == 52
    assert body["agents_status"]["total"] == 11
    assert len(body["recent_jobs"]) == 5
    assert {job["status"] for job in body["recent_jobs"]} >= {"COMPLETED", "FAILED", "CANCELLED"}


def test_seed_testbed_demo_api_loads_resettable_demo_data(client):
    response = client.post("/api/dashboard/demo-seed", data={"reset": True}, content_type="application/json")

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "loaded"
    assert body["reset"] is True
    assert body["scenario"] == "testbed_demo"
    assert body["asset_count"] == len(LATEST_ASSETS)
    assert body["latest_snapshot_id"] == CbomSnapshot.objects.get(serial_number="testbed-demo-latest").id
    assert body["baseline_snapshot_id"] == CbomSnapshot.objects.get(serial_number="testbed-demo-baseline").id
    assert Target.objects.count() == 31
