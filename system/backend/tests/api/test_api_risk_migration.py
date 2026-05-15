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
    assert isinstance(item["score"], int)
    assert set(item["factors"]) == {"a", "d", "e", "l", "c"}
    assert item["factors"]["a"] == 0.95


def test_api_rsk_002b_empty_tier_filter_returns_empty_page(client):
    snapshot = create_snapshot()

    response = client.get(f"/api/snapshots/{snapshot.id}/risks?tier=CRITICAL")

    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["items"] == []


def test_api_rsk_002c_list_snapshot_risks_applies_max_score_sort_and_missing_snapshot(client):
    snapshot = create_snapshot()
    low = create_asset(snapshot=snapshot, name="low-risk", bom_ref="risk:low")
    high = create_asset(snapshot=snapshot, name="high-risk", bom_ref="risk:high")
    create_risk_score(low, score=20.0, tier="LOW")
    create_risk_score(high, score=80.0, tier="HIGH")

    response = client.get(f"/api/snapshots/{snapshot.id}/risks?max_score=50&sort=score")
    missing = client.get("/api/snapshots/999999/risks")

    assert response.status_code == 200
    assert [item["asset_id"] for item in response.json()["items"]] == [low.id]
    assert missing.status_code == 404


def test_api_rsk_002d_list_snapshot_risks_validates_min_score_and_sort(client):
    snapshot = create_snapshot()

    negative = client.get(f"/api/snapshots/{snapshot.id}/risks?min_score=-1")
    too_high = client.get(f"/api/snapshots/{snapshot.id}/risks?min_score=101")
    non_numeric = client.get(f"/api/snapshots/{snapshot.id}/risks?min_score=abc")
    invalid_sort = client.get(f"/api/snapshots/{snapshot.id}/risks?sort=name")

    assert negative.status_code == 422
    assert too_high.status_code == 422
    assert non_numeric.status_code == 422
    assert invalid_sort.status_code == 422


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
        data={
            "weights": {"wA": 1.0, "wD": 1.0, "wE": 1.0, "wL": 1.0, "wC": 1.0},
            "persist_weights_as_default": True,
        },
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
        asset = create_asset(snapshot=snapshot, name=f"asset-{score}", bom_ref=f"asset:{score}")
        create_risk_score(asset, score=score, tier="HIGH")

    response = client.get(f"/api/snapshots/{snapshot.id}/risks/top?n=2")

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) <= 2
    assert body["limit"] == 2
    assert [item["score"] for item in body["items"]] == [95, 80]


def test_api_rsk_009b_top_risks_returns_404_for_missing_snapshot(client):
    response = client.get("/api/snapshots/999999/risks/top")

    assert response.status_code == 404


def test_api_rsk_010_recompute_requires_weights(client):
    snapshot = create_snapshot()

    response = client.post(
        f"/api/snapshots/{snapshot.id}/recompute",
        data={"persist_weights_as_default": True},
        content_type="application/json",
    )

    assert response.status_code == 422


def test_api_rsk_011_recompute_rejects_incomplete_or_out_of_range_weights(client):
    snapshot = create_snapshot()

    incomplete = client.post(
        f"/api/snapshots/{snapshot.id}/recompute",
        data={"weights": {"wA": 1.0}},
        content_type="application/json",
    )
    out_of_range = client.post(
        f"/api/snapshots/{snapshot.id}/recompute",
        data={"weights": {"wA": 0.1, "wD": 1.0, "wE": 1.0, "wL": 1.0, "wC": 1.0}},
        content_type="application/json",
    )

    assert incomplete.status_code == 422
    assert out_of_range.status_code == 422


def test_api_mig_001_migration_plan_returns_recommendation_page(client):
    snapshot = create_snapshot()
    asset = create_asset(snapshot=snapshot, asset_type="certificate", algorithm="RSA-2048")
    create_risk_score(asset, score=95.0, tier="CRITICAL")

    response = client.get(f"/api/snapshots/{snapshot.id}/migration-plan?tier=CRITICAL,HIGH&asset_type=certificate")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert {"asset_id", "asset_name", "asset_type", "asset_purpose", "current", "recommendation", "alternatives", "risk_score", "tier"} <= set(item)
    assert item["asset_purpose"] == "digital_signature"
    assert item["recommendation"]["strategy"] in {"replace", "hybrid", "no_change"}
    assert {
        "strategy",
        "target_algorithm",
        "target_algorithm_set",
        "final_algorithm_set",
        "phase",
        "blockers",
        "rollback",
        "validation",
        "rationale",
        "confidence",
    } <= set(item["recommendation"])
    assert {"score", "level", "blockers", "enablers"} <= set(item["agility"])
    assert item["playbook"]


def test_api_mig_004_migration_plan_applies_contract_filters_and_pagination(client):
    snapshot = create_snapshot()
    target_a = create_target(host="a.testbed.local")
    target_b = create_target(host="b.testbed.local")
    asset_a = create_asset(snapshot=snapshot, target=target_a, asset_type="certificate", bom_ref="mig:a")
    asset_b = create_asset(snapshot=snapshot, target=target_b, asset_type="key", bom_ref="mig:b")
    asset_c = create_asset(snapshot=snapshot, target=target_a, asset_type="certificate", bom_ref="mig:c")
    create_risk_score(asset_a, score=95.0, tier="CRITICAL")
    create_risk_score(asset_b, score=80.0, tier="HIGH")
    create_risk_score(asset_c, score=30.0, tier="LOW")

    response = client.get(
        f"/api/snapshots/{snapshot.id}/migration-plan"
        f"?min_score=70&tier=CRITICAL,HIGH&asset_type=certificate&target_id={target_a.id}"
        f"&asset_ids={asset_a.id},{asset_b.id}&offset=0&limit=1"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["offset"] == 0
    assert body["limit"] == 1
    assert [item["asset_id"] for item in body["items"]] == [asset_a.id]


def test_api_mig_005_migration_plan_validates_score_and_missing_snapshot(client):
    snapshot = create_snapshot()

    low_response = client.get(f"/api/snapshots/{snapshot.id}/migration-plan?min_score=-1")
    high_response = client.get(f"/api/snapshots/{snapshot.id}/migration-plan?min_score=101")
    missing_response = client.get("/api/snapshots/999999/migration-plan")

    assert low_response.status_code == 422
    assert high_response.status_code == 422
    assert missing_response.status_code == 404


def test_api_mig_006_migration_plan_marks_rsa_hybrid_and_safe_no_change(client):
    snapshot = create_snapshot()
    rsa_asset = create_asset(snapshot=snapshot, algorithm="RSA-2048", algorithm_family="RSA", bom_ref="mig:rsa")
    pqc_asset = create_asset(snapshot=snapshot, algorithm="ML-DSA-65", algorithm_family="ML-DSA", bom_ref="mig:pqc")
    create_risk_score(rsa_asset, score=95.4, tier="CRITICAL")
    create_risk_score(pqc_asset, score=42.2, tier="MEDIUM")

    response = client.get(f"/api/snapshots/{snapshot.id}/migration-plan?asset_ids={rsa_asset.id},{pqc_asset.id}")

    assert response.status_code == 200
    by_asset = {item["asset_id"]: item for item in response.json()["items"]}
    assert by_asset[rsa_asset.id]["recommendation"]["strategy"] == "hybrid"
    assert by_asset[rsa_asset.id]["asset_purpose"] == "digital_signature"
    assert by_asset[rsa_asset.id]["recommendation"]["target_algorithm_set"] == ["RSA-2048", "ML-DSA-65"]
    assert by_asset[rsa_asset.id]["recommendation"]["phase"] == "hybrid_first"
    assert by_asset[rsa_asset.id]["current"]["quantum_vulnerable"] is True
    assert by_asset[rsa_asset.id]["risk_score"] == 95
    assert by_asset[pqc_asset.id]["recommendation"]["strategy"] == "no_change"
    assert by_asset[pqc_asset.id]["asset_purpose"] == "digital_signature"
    assert by_asset[pqc_asset.id]["current"]["quantum_vulnerable"] is False
    assert by_asset[pqc_asset.id]["recommendation"]["phase"] == "monitor"


def test_api_mig_006b_migration_plan_maps_rsa_key_agreement_to_ml_kem(client):
    snapshot = create_snapshot()
    key_exchange_asset = create_asset(
        snapshot=snapshot,
        name="legacy RSA key exchange",
        asset_type="key_agreement",
        algorithm="RSA-2048",
        algorithm_family="RSA",
        bom_ref="mig:rsa:key-agreement",
    )
    certificate_asset = create_asset(
        snapshot=snapshot,
        name="legacy RSA certificate",
        asset_type="certificate",
        algorithm="RSA-2048",
        algorithm_family="RSA",
        bom_ref="mig:rsa:certificate",
    )
    create_risk_score(key_exchange_asset, score=88.0, tier="HIGH")
    create_risk_score(certificate_asset, score=87.0, tier="HIGH")

    response = client.get(f"/api/snapshots/{snapshot.id}/migration-plan?asset_ids={key_exchange_asset.id},{certificate_asset.id}")

    assert response.status_code == 200
    by_asset = {item["asset_id"]: item for item in response.json()["items"]}
    assert by_asset[key_exchange_asset.id]["asset_purpose"] == "key_exchange"
    assert by_asset[key_exchange_asset.id]["recommendation"]["target_algorithm_set"] == ["X25519", "ML-KEM-768"]
    assert by_asset[key_exchange_asset.id]["recommendation"]["final_algorithm_set"] == ["ML-KEM-768"]
    assert by_asset[certificate_asset.id]["asset_purpose"] == "digital_signature"
    assert by_asset[certificate_asset.id]["recommendation"]["target_algorithm_set"] == ["RSA-2048", "ML-DSA-65"]


def test_api_mig_006c_migration_plan_maps_ecdsa_p256_alias_to_ml_dsa(client):
    snapshot = create_snapshot()
    ecdsa_asset = create_asset(
        snapshot=snapshot,
        name="curve-only ECDSA certificate",
        asset_type="certificate",
        algorithm="prime256v1",
        algorithm_family="",
        bom_ref="mig:ecdsa:p256-alias",
    )
    create_risk_score(ecdsa_asset, score=84.0, tier="HIGH")

    response = client.get(f"/api/snapshots/{snapshot.id}/migration-plan?asset_ids={ecdsa_asset.id}")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["asset_purpose"] == "digital_signature"
    assert item["current"]["quantum_vulnerable"] is True
    assert item["recommendation"]["target_algorithm_set"] == ["ECDSA P-256", "ML-DSA-65"]
    assert item["recommendation"]["final_algorithm_set"] == ["ML-DSA-65"]


def test_api_mig_007_migration_plan_rejects_non_integer_asset_ids(client):
    snapshot = create_snapshot()

    response = client.get(f"/api/snapshots/{snapshot.id}/migration-plan?asset_ids=abc")

    assert response.status_code == 422
    assert response.json()["details"]["parameter"] == "asset_ids"


def test_api_mig_002_migration_impact_calculates_selected_assets_only(client):
    snapshot = create_snapshot()
    target = create_target(host="impact.testbed.local")
    asset_a = create_asset(snapshot=snapshot, target=target, bom_ref="asset:a")
    asset_b = create_asset(snapshot=snapshot, target=target, bom_ref="asset:b")
    create_asset(bom_ref="asset:other")

    response = client.get(
        f"/api/snapshots/{snapshot.id}/migration-plan/impact?asset_ids={asset_a.id},{asset_b.id}"
    )

    assert response.status_code == 200
    assert response.json() == {
        "selected_count": 2,
        "hosts": ["impact.testbed.local"],
        "services": ["impact.testbed.local:443"],
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
