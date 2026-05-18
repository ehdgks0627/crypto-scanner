import pytest
from django.core.management import call_command

from apps.agents.models import Agent
from apps.core.management.commands.seed_testbed_demo import (
    DEMO_FULL_PIPELINE_RUNTIME_MINUTES,
    DEMO_SCAN_RUNTIME_MINUTES,
    DORMANT_PRIVATE_KEY_PATHS,
    EXPIRING_CERTIFICATE_DAYS,
    HOMEPAGE_CONTEXT_INFERENCES,
    LATEST_ASSETS,
    SCAN_SCANNERS,
    TESTBED_TARGET_IPS,
)
from apps.discoveries.models import Discovery
from apps.assets.models import AssetContextOverride
from apps.jobs.models import ScanRunLog
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
    for hostname, ip in TESTBED_TARGET_IPS.items():
        assert set(Target.objects.filter(host=hostname).values_list("ip", flat=True)) == {ip}
    web_target = Target.objects.get(host="web.testbed.local", port=443, transport="TCP")
    assert web_target.context["service_role"] == "customer_portal"
    assert web_target.context["homepage_inference"]["source"] == "homepage"
    assert web_target.context["homepage_inference"]["title"] == HOMEPAGE_CONTEXT_INFERENCES["web.testbed.local"]["homepage_inference"]["title"]
    discovery = Discovery.objects.get(cidr="172.20.0.0/16")
    assert discovery.endpoints.count() == 32
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
    assert body["kpis"]["automated_inventory_runtime_minutes_per_scan"]["value"] == DEMO_SCAN_RUNTIME_MINUTES
    assert body["kpis"]["automated_inventory_runtime_minutes_per_scan"]["scan_job_id"] == latest.scan_job_id
    assert body["kpis"]["full_pipeline_runtime_minutes"]["value"] == DEMO_FULL_PIPELINE_RUNTIME_MINUTES
    assert body["kpis"]["full_pipeline_runtime_minutes"]["scan_job_id"] == latest.scan_job_id
    assert body["by_tier"]["CRITICAL"] == 18
    assert body["by_tier"]["HIGH"] == 31
    assert body["quantum_vulnerable_ratio"]["vulnerable"] == 52
    assert body["agents_status"]["total"] == 11
    assert body["context_inferences"][0]["service_role"] == "customer_portal"
    assert body["context_inferences"][0]["title"] == "Customer Portal Login"
    assert len(body["recent_jobs"]) == 5
    assert {job["status"] for job in body["recent_jobs"]} >= {"COMPLETED", "FAILED", "CANCELLED"}

    agent_scanners = [scanner for scanner in SCAN_SCANNERS if scanner.startswith("agent.")]
    agent_run_logs = ScanRunLog.objects.filter(
        async_job=latest.scan_job.async_job,
        scanner_kind__startswith="agent.",
    ).order_by("scanner_kind")
    assert agent_run_logs.count() == Target.objects.filter(agent_enabled=True).count() * len(agent_scanners)
    assert set(agent_run_logs.values_list("scanner_kind", flat=True)) == set(agent_scanners)
    assert set(agent_run_logs.values_list("status", flat=True)) == {"COMPLETED"}

    dormant_assets = [asset for asset in latest.assets.all() if (asset.metadata or {}).get("dormant") is True]
    assert {asset.bom_ref for asset in dormant_assets} == set(DORMANT_PRIVATE_KEY_PATHS)
    for asset in dormant_assets:
        metadata = asset.metadata
        assert metadata["source_scanners"] == ["agent.private_key_files"]
        assert metadata["private_key_paths"] == DORMANT_PRIVATE_KEY_PATHS[asset.bom_ref]
        assert not {"private_key", "private_key_pem", "key_material", "pem"} & set(metadata)


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


def test_seed_demo_labels_applies_srv_01_context():
    call_command("seed_testbed_demo", "--reset")
    call_command("seed_demo_labels")

    target = Target.objects.get(host="api-gateway.testbed.local", port=8443, transport="TCP")
    assert target.display_name == "srv-01 - 외부 결제 API"
    assert target.context["host_alias"] == "srv-01"
    assert target.context["service_role"] == "edge-proxy"
    assert target.context["sensitivity"] == "critical"
    assert target.context["lifespan_years"] == 7
    assert target.context["demo_label"] == {
        "role": "edge-proxy",
        "data_classes": ["PII", "payment"],
        "partners": ["PG-A"],
        "retention": "7y",
    }

    latest = CbomSnapshot.objects.get(serial_number="testbed-demo-latest")
    asset = latest.assets.get(bom_ref="tls:api-gateway:leaf:rsa")
    assert asset.metadata["host_alias"] == "srv-01"
    assert asset.metadata["host_role"] == "edge-proxy"
    assert asset.metadata["data_tags"] == ["PII", "payment"]
    assert asset.metadata["partners"] == ["PG-A"]
    assert asset.metadata["retention_policy"] == "7y"
    assert asset.metadata["discovered_by"] == ["discovery_agent", "host_agent"]

    override = AssetContextOverride.objects.get(asset=asset)
    assert override.service_role == "edge-proxy"
    assert override.sensitivity == "critical"
    assert override.lifespan_years == 7
