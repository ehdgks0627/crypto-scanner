import pytest

from tests.api.factories import create_asset, create_snapshot, create_target


pytestmark = pytest.mark.django_db


def _metrics(handshake_p95=100, ttfb_p95=200, failure_rate=0.0, throughput_rps=1000):
    return {
        "tcp_connect_ms": {"p50": 8, "p95": 15},
        "handshake_ms": {"p50": 40, "p95": handshake_p95},
        "ttfb_ms": {"p50": 100, "p95": ttfb_p95},
        "total_request_ms": {"p50": 160, "p95": ttfb_p95 + 60},
        "throughput_rps": throughput_rps,
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
    assert run["post_migration_snapshot_id"] is None
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
    assert result["protocol"] == "TLS"
    assert result["response_code"] is None
    assert result["failure_reason"] is None
    assert result["metrics"]["protocol"] == "TLS"
    assert result["metrics"]["handshake_success_rate"] == 1.0

    detail = client.get(f"/api/snapshots/{snapshot.id}/performance-runs/{run['id']}").json()
    assert detail["status"] == "RUNNING"
    assert detail["summary"]["by_status"]["PASS"] == 1
    assert detail["summary"]["average_metrics"]["handshake_success_rate"] == 1.0
    assert detail["summary"]["by_protocol"]["TLS"]["average_metrics"]["handshake_success_rate"] == 1.0
    assert detail["results"][0]["bom_ref"] == "tls:web:leaf"


def test_api_perf_001b_auto_start_enqueues_availability_runner(client):
    from apps.jobs.models import QueuedTask

    snapshot = create_snapshot()
    create_asset(snapshot=snapshot, bom_ref="tls:web:auto-start")

    response = client.post(
        f"/api/snapshots/{snapshot.id}/performance-runs",
        data={"trigger": "manual", "profile": "smoke", "auto_start": True},
        content_type="application/json",
    )

    assert response.status_code == 201
    run = response.json()
    task = QueuedTask.objects.get(task_name="performance_run")
    assert task.payload == {"run_id": run["id"], "snapshot_id": snapshot.id}


def test_api_perf_001c_worker_records_availability_results(monkeypatch):
    from apps.jobs.models import QueuedTask
    from apps.performance import runner, services, worker

    snapshot = create_snapshot()
    target = create_target(host="web.testbed.local", port=443, protocol_hint="TLS")
    asset = create_asset(snapshot=snapshot, target=target, bom_ref="tls:web:worker")
    run = services.create_run(snapshot, {"trigger": "manual", "profile": "smoke"})
    services.enqueue_run(run)

    monkeypatch.setattr(
        runner,
        "measure_target",
        lambda target, profile: runner.Measurement(
            compatibility_status="PASS",
            negotiated_algorithm="TLSv1.3 TLS_AES_256_GCM_SHA384",
            metrics={
                "protocol": "TLS",
                "tcp_connect_ms": {"p50": 3, "p95": 3, "samples": 1},
                "handshake_ms": {"p50": 12, "p95": 12, "samples": 1},
                "successful_handshakes": 1,
                "failed_handshakes": 0,
                "total_handshakes": 1,
                "failure_rate": 0,
                "timeout_rate": 0,
                "response_code": "tls_ok",
            },
        ),
    )

    result = worker.process_next_performance_run_task()

    run.refresh_from_db()
    task = QueuedTask.objects.get(task_name="performance_run")
    assert result["measured_assets"] == 1
    assert run.status == "COMPLETED"
    assert task.status == "COMPLETED"
    perf_result = run.results.get(asset=asset)
    assert perf_result.status == "PASS"
    assert perf_result.metrics["handshake_success_rate"] == 1.0


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
        data={"asset_id": baseline_asset.id, "metrics": _metrics(handshake_p95=100, ttfb_p95=200, throughput_rps=1000)},
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
        data={"asset_id": candidate_asset.id, "metrics": _metrics(handshake_p95=125, ttfb_p95=212, throughput_rps=820)},
        content_type="application/json",
    )

    assert result_response.status_code == 201
    result = result_response.json()
    assert result["status"] == "WARN"
    assert result["metrics"]["baseline_metrics"]["handshake_ms"]["p95"] == 100
    assert result["metrics"]["baseline_metrics"]["throughput_rps"] == 1000
    assert result["deltas"]["handshake_p95_percent"] == 25.0
    assert result["deltas"]["throughput_rps_percent"] == -18.0
    assert result["recommendation"] == "canary_more"
    detail = client.get(f"/api/snapshots/{candidate_snapshot.id}/performance-runs/{candidate_run['id']}").json()
    assert detail["summary"]["latency_comparison"]["handshake_ms"] == {
        "baseline_p95": 100.0,
        "candidate_p95": 125.0,
        "delta_percent": 25.0,
    }
    assert detail["summary"]["throughput_comparison"]["throughput_rps"] == {
        "baseline_value": 1000.0,
        "candidate_value": 820.0,
        "delta_percent": -18.0,
    }


def test_api_perf_003_post_migration_run_auto_links_previous_snapshot_as_baseline(client):
    baseline_snapshot = create_snapshot(serial_number="pre-migration")
    candidate_snapshot = create_snapshot(serial_number="post-migration")

    response = client.post(
        f"/api/snapshots/{candidate_snapshot.id}/performance-runs",
        data={"trigger": "post_migration", "profile": "smoke"},
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["snapshot_id"] == candidate_snapshot.id
    assert body["baseline_snapshot_id"] == baseline_snapshot.id
    assert body["post_migration_snapshot_id"] == candidate_snapshot.id

    candidate_snapshot.refresh_from_db()
    migration = candidate_snapshot.summary["migration"]
    assert migration["phase"] == "post_migration"
    assert migration["pre_migration_snapshot_id"] == baseline_snapshot.id
    assert migration["post_migration_snapshot_id"] == candidate_snapshot.id
    assert migration["latest_performance_run_id"] == body["id"]
    assert migration["post_migration_runs"] == [
        {
            "run_id": body["id"],
            "profile": "smoke",
            "baseline_snapshot_id": baseline_snapshot.id,
            "post_migration_snapshot_id": candidate_snapshot.id,
        }
    ]


def test_api_perf_004_post_migration_run_requires_pre_migration_snapshot(client):
    snapshot = create_snapshot(serial_number="first-snapshot")

    response = client.post(
        f"/api/snapshots/{snapshot.id}/performance-runs",
        data={"trigger": "post_migration", "profile": "smoke"},
        content_type="application/json",
    )

    assert response.status_code == 422
    assert response.json()["error"] == "unprocessable"
    assert response.json()["details"]["snapshot_id"] == snapshot.id


def test_api_perf_005_rejects_foreign_asset_for_run(client):
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


def test_api_perf_006_lists_asset_performance_history(client):
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


def test_api_perf_007_records_tls_handshake_success_rate_from_counts(client):
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


def test_api_perf_008_records_ssh_handshake_success_rate_by_protocol(client):
    snapshot = create_snapshot()
    ssh_target = create_target(host="ssh.testbed.local", port=22, protocol_hint="SSH")
    asset = create_asset(
        snapshot=snapshot,
        target=ssh_target,
        bom_ref="ssh:host:rsa",
        asset_type="ssh_host_key",
        algorithm="RSA-3072",
        algorithm_family="RSA",
    )
    run = client.post(f"/api/snapshots/{snapshot.id}/performance-runs", data={}, content_type="application/json").json()

    response = client.post(
        f"/api/snapshots/{snapshot.id}/performance-runs/{run['id']}/results",
        data={
            "asset_id": asset.id,
            "negotiated_algorithm": "curve25519-sha256 + ssh-rsa",
            "metrics": {
                "successful_handshakes": 20,
                "failed_handshakes": 0,
                "handshake_ms": {"p50": 30, "p95": 55, "samples": 20},
            },
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["protocol"] == "SSH"
    assert body["metrics"]["protocol"] == "SSH"
    assert body["metrics"]["total_handshakes"] == 20
    assert body["metrics"]["handshake_success_rate"] == 1.0

    detail = client.get(f"/api/snapshots/{snapshot.id}/performance-runs/{run['id']}").json()
    assert detail["summary"]["by_protocol"]["SSH"]["total_results"] == 1
    assert detail["summary"]["by_protocol"]["SSH"]["average_metrics"]["handshake_success_rate"] == 1.0


def test_api_perf_009_records_ike_negotiation_success_rate_by_protocol(client):
    snapshot = create_snapshot()
    ike_target = create_target(host="ipsec.testbed.local", port=500, protocol_hint="IKE", transport="UDP")
    asset = create_asset(
        snapshot=snapshot,
        target=ike_target,
        bom_ref="ike:policy:ipsec",
        asset_type="protocol",
        algorithm="IKEv2 DH group14",
        algorithm_family="DH",
    )
    run = client.post(f"/api/snapshots/{snapshot.id}/performance-runs", data={}, content_type="application/json").json()

    response = client.post(
        f"/api/snapshots/{snapshot.id}/performance-runs/{run['id']}/results",
        data={
            "asset_id": asset.id,
            "negotiated_algorithm": "IKEv2 DH group14 + AES-GCM",
            "metrics": {
                "successful_negotiations": 10,
                "failed_negotiations": 0,
                "handshake_ms": {"p50": 45, "p95": 80, "samples": 10},
            },
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["protocol"] == "IKE"
    assert body["metrics"]["protocol"] == "IKE"
    assert body["metrics"]["total_negotiations"] == 10
    assert body["metrics"]["negotiation_success_rate"] == 1.0
    assert body["metrics"]["availability_success_rate"] == 1.0

    detail = client.get(f"/api/snapshots/{snapshot.id}/performance-runs/{run['id']}").json()
    assert detail["summary"]["by_protocol"]["IKE"]["total_results"] == 1
    assert detail["summary"]["by_protocol"]["IKE"]["average_metrics"]["negotiation_success_rate"] == 1.0


def test_api_perf_010_records_protocol_response_code_and_failure_reason(client):
    snapshot = create_snapshot()
    asset = create_asset(snapshot=snapshot, bom_ref="tls:web:alert")
    run = client.post(f"/api/snapshots/{snapshot.id}/performance-runs", data={}, content_type="application/json").json()

    response = client.post(
        f"/api/snapshots/{snapshot.id}/performance-runs/{run['id']}/results",
        data={
            "asset_id": asset.id,
            "compatibility_status": "FAIL",
            "metrics": {
                "response_code": "tls_alert_bad_certificate",
                "failure_reason": "certificate_verify_failed",
                "failure_rate": 1.0,
            },
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "FAIL"
    assert body["response_code"] == "tls_alert_bad_certificate"
    assert body["failure_reason"] == "certificate_verify_failed"
    assert body["metrics"]["response_code"] == "tls_alert_bad_certificate"
    assert body["metrics"]["failure_reason"] == "certificate_verify_failed"

    detail = client.get(f"/api/snapshots/{snapshot.id}/performance-runs/{run['id']}").json()
    protocol_summary = detail["summary"]["by_protocol"]["TLS"]
    assert protocol_summary["response_codes"] == {"tls_alert_bad_certificate": 1}
    assert protocol_summary["failure_reasons"] == {"certificate_verify_failed": 1}


def test_api_perf_011_records_client_compatibility_matrix(client):
    snapshot = create_snapshot()
    asset = create_asset(snapshot=snapshot, bom_ref="tls:web:legacy-client")
    run = client.post(f"/api/snapshots/{snapshot.id}/performance-runs", data={}, content_type="application/json").json()

    response = client.post(
        f"/api/snapshots/{snapshot.id}/performance-runs/{run['id']}/results",
        data={
            "asset_id": asset.id,
            "metrics": {
                "client_compatibility": [
                    {"profile": "modern_tls13", "status": "PASS", "response_code": "tls_ok"},
                    {
                        "profile": "legacy_tls12",
                        "status": "FAIL",
                        "response_code": "handshake_failure",
                        "failure_reason": "unsupported_signature_algorithm",
                    },
                ]
            },
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "FAIL"
    assert body["metrics"]["client_compatibility"][1]["profile"] == "legacy_tls12"
    assert body["metrics"]["client_compatibility"][1]["status"] == "FAIL"
    assert any(signal["reason"] == "client_legacy_tls12_compatibility_failed" for signal in body["signals"])

    detail = client.get(f"/api/snapshots/{snapshot.id}/performance-runs/{run['id']}").json()
    client_summary = detail["summary"]["client_compatibility"]
    assert client_summary["total_checks"] == 2
    assert client_summary["by_status"] == {"PASS": 1, "WARN": 0, "FAIL": 1, "ERROR": 0}
    assert client_summary["by_profile"]["legacy_tls12"]["failure_reasons"] == {"unsupported_signature_algorithm": 1}
    assert detail["summary"]["failure_paths"] == [
        {
            "protocol": "TLS",
            "client_profile": "legacy_tls12",
            "response_code": "handshake_failure",
            "failure_reason": "unsupported_signature_algorithm",
            "count": 1,
            "asset_refs": ["tls:web:legacy-client"],
            "status": "FAIL",
        }
    ]
