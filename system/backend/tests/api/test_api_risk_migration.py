import pytest

from tests.api.factories import assert_job_envelope, create_asset, create_risk_score, create_snapshot, create_target


pytestmark = pytest.mark.django_db


def test_api_rsk_001_get_default_risk_weights(client):
    response = client.get("/api/risk/weights")

    assert response.status_code == 200
    body = response.json()
    assert {"wA", "wD", "wE", "wL", "wC", "updated_at"} <= set(body)


def test_api_rsk_002_list_snapshot_risks_with_filters(client):
    snapshot = create_snapshot()
    critical_asset = create_asset(snapshot=snapshot, name="critical cert")
    create_risk_score(critical_asset, score=95.0, tier="CRITICAL")
    low_asset = create_asset(snapshot=snapshot, name="low cert")
    create_risk_score(low_asset, score=25.0, tier="LOW")

    response = client.get(f"/api/snapshots/{snapshot.id}/risks?tier=CRITICAL,HIGH&min_score=70&limit=20&offset=0")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert {
        "asset_id",
        "asset_name",
        "asset_type",
        "score",
        "tier",
        "factors",
        "computed_at",
    } <= set(item)
    assert item["tier"] == "CRITICAL"
    assert item["score"] >= 70


def test_api_rsk_003_put_weights_does_not_accept_updated_at(client):
    response = client.put(
        "/api/risk/weights",
        data={"wA": 1.1, "wD": 1.2, "wE": 1.3, "wL": 1.4, "wC": 1.5},
        content_type="application/json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["wA"] == 1.1
    assert body["wC"] == 1.5
    assert body["updated_at"] is not None


def test_api_rsk_004_put_weights_rejects_updated_at(client):
    original = client.get("/api/risk/weights").json()

    response = client.put(
        "/api/risk/weights",
        data={"wA": 1.1, "wD": 1.2, "wE": 1.3, "wL": 1.4, "wC": 1.5, "updated_at": "now"},
        content_type="application/json",
    )

    assert response.status_code == 422
    assert response.json()["error"] == "unprocessable"
    assert client.get("/api/risk/weights").json()["wA"] == original["wA"]


def test_api_rsk_005_put_weights_rejects_out_of_range_values(client):
    response = client.put(
        "/api/risk/weights",
        data={"wA": 0.1, "wD": 1.0, "wE": 1.0, "wL": 1.0, "wC": 1.0},
        content_type="application/json",
    )

    assert response.status_code == 422
    assert "wA" in str(response.json()["details"])


def test_api_rsk_006_recompute_returns_recompute_job_envelope(client):
    snapshot = create_snapshot()

    response = client.post(
        f"/api/snapshots/{snapshot.id}/recompute",
        data={"weights": {"wA": 1.0, "wD": 1.0, "wE": 1.0, "wL": 1.0, "wC": 1.0}, "persist": True},
        content_type="application/json",
    )

    assert response.status_code == 202
    body = response.json()
    assert_job_envelope(body)
    assert body["kind"] == "recompute"
    assert body["resource"]["kind"] == "recompute"
    assert body["resource"]["id"] == body["id"]
    assert body["result"] is None


def test_api_rsk_007_completed_recompute_returns_updated_scores_count(client):
    from tests.api.factories import create_async_job

    job = create_async_job(
        kind="recompute",
        status="COMPLETED",
        result={"snapshot_id": 56, "updated_scores_count": 142},
    )

    response = client.get(f"/api/jobs/{job.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "recompute"
    assert body["status"] == "COMPLETED"
    assert body["result"]["snapshot_id"] == 56
    assert body["result"]["updated_scores_count"] == 142


def test_api_rsk_008_recompute_enqueue_failure_returns_503(client, monkeypatch):
    from apps.jobs.models import AsyncJob
    from apps.risk import services

    snapshot = create_snapshot()

    def fail_enqueue(async_job):
        raise services.EnqueueUnavailable("queue unavailable")

    monkeypatch.setattr(services, "enqueue_recompute", fail_enqueue)

    response = client.post(
        f"/api/snapshots/{snapshot.id}/recompute",
        data={"weights": {"wA": 1.0, "wD": 1.0, "wE": 1.0, "wL": 1.0, "wC": 1.0}},
        content_type="application/json",
    )

    assert response.status_code == 503
    assert response.json()["error"] == "service_unavailable"
    assert AsyncJob.objects.count() == 0


def test_api_rsk_009_top_risks_returns_limited_page(client):
    snapshot = create_snapshot()
    scores = [95.0, 80.0, 70.0]
    for score in scores:
        asset = create_asset(snapshot=snapshot, name=f"asset-{score}", natural_key=f"asset:{score}")
        create_risk_score(asset, score=score, tier="HIGH")

    response = client.get(f"/api/snapshots/{snapshot.id}/risks/top?n=2")

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) <= 2
    assert body["limit"] == 2
    assert [item["score"] for item in body["items"]] == [95.0, 80.0]


def test_api_mig_001_migration_plan_returns_recommendation_page(client):
    snapshot = create_snapshot()
    asset = create_asset(snapshot=snapshot, asset_type="certificate", algorithm="RSA-2048")
    create_risk_score(asset, score=95.0, tier="CRITICAL")

    response = client.get(f"/api/snapshots/{snapshot.id}/migration-plan?tier=CRITICAL,HIGH&asset_type=certificate")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert {"current", "recommendation", "alternatives", "risk_score", "tier"} <= set(item)
    assert item["recommendation"]["strategy"] in {"replace", "hybrid", "no_change"}


def test_api_mig_002_migration_impact_calculates_selected_assets_only(client):
    snapshot = create_snapshot()
    target = create_target(host="impact.testbed.local")
    asset_a = create_asset(snapshot=snapshot, target=target, natural_key="asset:a")
    asset_b = create_asset(snapshot=snapshot, target=target, natural_key="asset:b")
    create_asset(natural_key="asset:other")

    response = client.get(
        f"/api/snapshots/{snapshot.id}/migration-plan/impact?asset_ids={asset_a.id},{asset_b.id}"
    )

    assert response.status_code == 200
    assert response.json() == {
        "selected_count": 2,
        "hosts": 1,
        "services": 1,
        "cert_reissues": 2,
        "config_changes": 2,
        "key_regens": 2,
        "estimated_downtime_min": 30,
    }


def test_api_mig_003_migration_impact_rejects_invalid_asset_ids(client):
    snapshot = create_snapshot()
    asset = create_asset(snapshot=snapshot)
    foreign_asset = create_asset()

    empty_response = client.get(f"/api/snapshots/{snapshot.id}/migration-plan/impact?asset_ids=")
    foreign_response = client.get(
        f"/api/snapshots/{snapshot.id}/migration-plan/impact?asset_ids={asset.id},{foreign_asset.id}"
    )

    assert empty_response.status_code == 422
    assert empty_response.json()["error"] == "unprocessable"
    assert foreign_response.status_code == 422
    assert foreign_response.json()["details"]["invalid_asset_ids"] == [foreign_asset.id]
