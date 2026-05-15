import pytest

from tests.api.factories import create_asset, create_snapshot


pytestmark = pytest.mark.django_db


def _metrics(handshake_p95=100, ttfb_p95=200, failure_rate=0.0):
    return {
        "tcp_connect_ms": {"p50": 8, "p95": 15},
        "handshake_ms": {"p50": 40, "p95": handshake_p95},
        "ttfb_ms": {"p50": 100, "p95": ttfb_p95},
        "total_request_ms": {"p50": 160, "p95": ttfb_p95 + 60},
        "failure_rate": failure_rate,
        "timeout_rate": 0.0,
        "handshake_bytes_sent": 2800,
        "handshake_bytes_received": 4200,
    }


def test_api_perf_001_create_run_and_record_result(client):
    snapshot = create_snapshot()
    asset = create_asset(snapshot=snapshot, bom_ref="tls:web:leaf")

    run_response = client.post(
        f"/api/snapshots/{snapshot.id}/performance-runs",
        data={"trigger": "manual", "profile": "smoke", "environment": {"region": "testbed"}},
        content_type="application/json",
    )

    assert run_response.status_code == 201
    run = run_response.json()
    assert run["snapshot_id"] == snapshot.id
    assert run["status"] == "PENDING"
    assert run["summary"]["overall_status"] == "PENDING"

    result_response = client.post(
        f"/api/snapshots/{snapshot.id}/performance-runs/{run['id']}/results",
        data={
            "asset_id": asset.id,
            "compatibility_status": "PASS",
            "negotiated_algorithm": "ML-KEM-768+ECDHE",
            "metrics": _metrics(),
        },
        content_type="application/json",
    )

    assert result_response.status_code == 201
    result = result_response.json()
    assert result["asset_id"] == asset.id
    assert result["status"] == "PASS"
    assert result["recommendation"] == "proceed"
    assert result["metrics"]["handshake_success_rate"] == 1.0

    detail = client.get(f"/api/snapshots/{snapshot.id}/performance-runs/{run['id']}").json()
    assert detail["status"] == "RUNNING"
    assert detail["summary"]["by_status"]["PASS"] == 1
    assert detail["summary"]["average_metrics"]["handshake_success_rate"] == 1.0
    assert detail["results"][0]["bom_ref"] == "tls:web:leaf"


def test_api_perf_002_candidate_result_compares_to_baseline_by_bom_ref(client):
    baseline_snapshot = create_snapshot(serial_number="baseline")
    candidate_snapshot = create_snapshot(serial_number="candidate")
    baseline_asset = create_asset(snapshot=baseline_snapshot, bom_ref="tls:web:leaf")
    candidate_asset = create_asset(snapshot=candidate_snapshot, bom_ref="tls:web:leaf")

    baseline_run = client.post(
        f"/api/snapshots/{baseline_snapshot.id}/performance-runs",
        data={"profile": "smoke"},
        content_type="application/json",
    ).json()
    client.post(
        f"/api/snapshots/{baseline_snapshot.id}/performance-runs/{baseline_run['id']}/results",
        data={"asset_id": baseline_asset.id, "metrics": _metrics(handshake_p95=100, ttfb_p95=200)},
        content_type="application/json",
    )
    client.patch(
        f"/api/snapshots/{baseline_snapshot.id}/performance-runs/{baseline_run['id']}",
        data={"status": "COMPLETED"},
        content_type="application/json",
    )

    candidate_run = client.post(
        f"/api/snapshots/{candidate_snapshot.id}/performance-runs",
        data={"baseline_snapshot_id": baseline_snapshot.id, "profile": "smoke", "trigger": "post_migration"},
        content_type="application/json",
    ).json()
    result_response = client.post(
        f"/api/snapshots/{candidate_snapshot.id}/performance-runs/{candidate_run['id']}/results",
        data={"asset_id": candidate_asset.id, "metrics": _metrics(handshake_p95=125, ttfb_p95=212)},
        content_type="application/json",
    )

    assert result_response.status_code == 201
    result = result_response.json()
    assert result["status"] == "WARN"
    assert result["deltas"]["handshake_p95_percent"] == 25.0
    assert result["recommendation"] == "canary_more"


def test_api_perf_003_rejects_foreign_asset_for_run(client):
    snapshot = create_snapshot()
    foreign_asset = create_asset()
    run = client.post(f"/api/snapshots/{snapshot.id}/performance-runs", data={}, content_type="application/json").json()

    response = client.post(
        f"/api/snapshots/{snapshot.id}/performance-runs/{run['id']}/results",
        data={"asset_id": foreign_asset.id, "metrics": _metrics()},
        content_type="application/json",
    )

    assert response.status_code == 422
    assert response.json()["details"]["asset_snapshot_id"] == foreign_asset.snapshot_id


def test_api_perf_004_lists_asset_performance_history(client):
    snapshot = create_snapshot()
    asset = create_asset(snapshot=snapshot, bom_ref="tls:web:history")
    run = client.post(f"/api/snapshots/{snapshot.id}/performance-runs", data={}, content_type="application/json").json()
    client.post(
        f"/api/snapshots/{snapshot.id}/performance-runs/{run['id']}/results",
        data={"asset_id": asset.id, "metrics": _metrics()},
        content_type="application/json",
    )

    response = client.get(f"/api/assets/{asset.id}/performance-history")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["run_id"] == run["id"]


def test_api_perf_005_records_tls_handshake_success_rate_from_counts(client):
    snapshot = create_snapshot()
    asset = create_asset(snapshot=snapshot, bom_ref="tls:web:success-rate")
    run = client.post(f"/api/snapshots/{snapshot.id}/performance-runs", data={}, content_type="application/json").json()

    response = client.post(
        f"/api/snapshots/{snapshot.id}/performance-runs/{run['id']}/results",
        data={
            "asset_id": asset.id,
            "metrics": {
                "successful_handshakes": 19,
                "failed_handshakes": 1,
                "handshake_ms": {"p50": 40, "p95": 120, "samples": 20},
            },
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "FAIL"
    assert body["metrics"]["total_handshakes"] == 20
    assert body["metrics"]["handshake_success_rate"] == 0.95
    assert body["metrics"]["failure_rate"] == 0.05
    assert any(signal["reason"] == "handshake_success_rate_below_fail_threshold" for signal in body["signals"])
