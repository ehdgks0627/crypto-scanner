import pytest

from tests.api.factories import (
    TARGET_CONTEXT,
    create_asset,
    create_risk_score,
    create_snapshot,
    create_target,
)


pytestmark = pytest.mark.django_db


def test_api_snp_001_list_snapshots_returns_latest_first_page(client):
    older = create_snapshot(serial_number="older")
    latest = create_snapshot(serial_number="latest")
    create_asset(snapshot=latest)

    response = client.get("/api/snapshots?limit=20&offset=0")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["id"] == latest.id
    assert body["items"][1]["id"] == older.id
    assert {
        "id",
        "scan_job_id",
        "serial_number",
        "asset_count",
        "created_at",
        "summary",
        "validation_errors",
    } <= set(body["items"][0])


def test_api_snp_002_get_snapshot_detail(client):
    snapshot = create_snapshot(serial_number="snap-56")
    create_asset(snapshot=snapshot)

    response = client.get(f"/api/snapshots/{snapshot.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == snapshot.id
    assert body["serial_number"] == "snap-56"
    assert body["asset_count"] == 1
    assert {"scan_job_id", "created_at", "summary", "validation_errors"} <= set(body)


def test_api_snp_003_export_snapshot_returns_cbom_download(client):
    cbom = {"bomFormat": "CycloneDX", "components": [{"name": "web certificate"}]}
    snapshot = create_snapshot(serial_number="snap-56", cbom_json=cbom)

    response = client.get(f"/api/snapshots/{snapshot.id}/export")

    assert response.status_code == 200
    assert "attachment" in response.headers["Content-Disposition"]
    assert f"snapshot-{snapshot.id}.json" in response.headers["Content-Disposition"]
    assert response.json() == cbom


def test_api_snp_004_diff_snapshots_returns_summary(client):
    snapshot_a = create_snapshot(serial_number="snap-55")
    snapshot_b = create_snapshot(serial_number="snap-56")
    create_asset(snapshot=snapshot_a, natural_key="cert:unchanged", name="same")
    create_asset(snapshot=snapshot_a, natural_key="cert:removed", name="old")
    create_asset(snapshot=snapshot_b, natural_key="cert:unchanged", name="same")
    create_asset(snapshot=snapshot_b, natural_key="cert:added", name="new")
    create_asset(snapshot=snapshot_b, natural_key="cert:modified", name="changed")
    create_asset(snapshot=snapshot_a, natural_key="cert:modified", name="before")

    response = client.get(f"/api/snapshots/{snapshot_b.id}/diff?other={snapshot_a.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["snapshot_a"] == snapshot_a.id
    assert body["snapshot_b"] == snapshot_b.id
    assert body["unchanged_count"] == 1
    assert any(item["natural_key"] == "cert:added" for item in body["added"])
    assert any(item["natural_key"] == "cert:removed" for item in body["removed"])
    assert any(item["natural_key"] == "cert:modified" for item in body["modified"])


def test_api_ast_001_list_assets_with_filters_and_risk(client):
    snapshot = create_snapshot()
    cert = create_asset(snapshot=snapshot, asset_type="certificate", name="critical cert")
    create_risk_score(cert, score=95.0, tier="CRITICAL")
    low = create_asset(snapshot=snapshot, asset_type="certificate", name="low cert")
    create_risk_score(low, score=20.0, tier="LOW")

    response = client.get(
        f"/api/snapshots/{snapshot.id}/assets?asset_type=certificate&tier=CRITICAL,HIGH&sort=-risk_score"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["asset_type"] == "certificate"
    assert item["risk"]["tier"] == "CRITICAL"
    assert {"offset", "limit"} <= set(body)


def test_api_ast_002_get_asset_detail_with_context_sources(client):
    from apps.assets.models import AssetContextOverride

    target = create_target(context={**TARGET_CONTEXT, "criticality": "medium"})
    asset = create_asset(target=target)
    AssetContextOverride.objects.create(asset=asset, sensitivity="critical", criticality=None)

    response = client.get(f"/api/assets/{asset.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["effective_context"]["sensitivity"] == "critical"
    assert body["effective_context"]["criticality"] == "medium"
    assert body["context_override"]["criticality"] is None
    assert body["context_sources"]["sensitivity"] == "asset_override"
    assert body["context_sources"]["criticality"] == "target"


def test_api_ast_003_context_patch_distinguishes_omit_and_null(client):
    from apps.assets.models import AssetContextOverride

    target = create_target(
        context={
            **TARGET_CONTEXT,
            "sensitivity": "high",
            "criticality": "medium",
            "lifespan_years": 5,
        }
    )
    asset = create_asset(target=target)
    AssetContextOverride.objects.create(
        asset=asset,
        sensitivity="critical",
        criticality="high",
        lifespan_years=10,
    )

    response = client.patch(
        f"/api/assets/{asset.id}/context",
        data={"criticality": "critical", "lifespan_years": None},
        content_type="application/json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["context_override"]["sensitivity"] == "critical"
    assert body["context_override"]["criticality"] == "critical"
    assert body["context_override"]["lifespan_years"] is None
    assert body["effective_context"]["lifespan_years"] == 5
    assert body["context_sources"]["lifespan_years"] == "target"
    assert body["recompute_job_id"] is not None


def test_api_ast_004_context_patch_enqueue_failure_rolls_back(client, monkeypatch):
    from apps.assets import services
    from apps.assets.models import AssetContextOverride
    from apps.jobs.models import AsyncJob

    asset = create_asset()
    AssetContextOverride.objects.create(asset=asset, sensitivity="high")

    def fail_enqueue(async_job):
        raise services.EnqueueUnavailable("queue unavailable")

    monkeypatch.setattr(services, "enqueue_asset_recompute", fail_enqueue)

    response = client.patch(
        f"/api/assets/{asset.id}/context",
        data={"sensitivity": "critical"},
        content_type="application/json",
    )

    assert response.status_code == 503
    assert response.json()["error"] == "service_unavailable"
    override = AssetContextOverride.objects.get(asset=asset)
    assert override.sensitivity == "high"
    assert AsyncJob.objects.count() == 0


def test_api_ast_005_qualitative_request_updates_existing_record(client):
    from apps.assets.models import QualitativeAssessment

    asset = create_asset()
    assessment = QualitativeAssessment.objects.create(
        asset=asset,
        provider="stub",
        summary="old summary",
        threat_scenarios=[],
        migration_recommendation="old",
        confidence=0.2,
    )

    response = client.post(f"/api/assets/{asset.id}/qualitative")

    assert response.status_code == 200
    body = response.json()
    assert {
        "provider",
        "summary",
        "threat_scenarios",
        "migration_recommendation",
        "confidence",
        "generated_at",
    } <= set(body)
    assert QualitativeAssessment.objects.count() == 1
    assessment.refresh_from_db()
    assert assessment.summary == body["summary"]
