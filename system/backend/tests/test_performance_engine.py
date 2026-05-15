from performance_engine import evaluate_asset_performance, normalize_availability_metrics, summarize_results


def test_performance_engine_fails_on_latency_regression_above_fail_threshold():
    result = evaluate_asset_performance(
        metrics={
            "handshake_ms": {"p50": 40, "p95": 135},
            "ttfb_ms": {"p50": 90, "p95": 180},
            "failure_rate": 0.0,
            "timeout_rate": 0.0,
            "handshake_bytes_sent": 3000,
            "handshake_bytes_received": 4000,
        },
        baseline_metrics={
            "handshake_ms": {"p50": 35, "p95": 100},
            "ttfb_ms": {"p50": 90, "p95": 170},
            "handshake_bytes_sent": 2500,
            "handshake_bytes_received": 3500,
        },
        compatibility_status="PASS",
    )

    assert result["status"] == "FAIL"
    assert result["deltas"]["handshake_p95_percent"] == 35.0
    assert any(signal["reason"] == "handshake_p95_percent_above_fail_threshold" for signal in result["signals"])


def test_performance_engine_summarizes_status_counts_and_average_deltas():
    summary = summarize_results(
        [
            {"status": "PASS", "deltas": {"handshake_p95_percent": 4}, "metrics": {"handshake_success_rate": 1.0}},
            {"status": "WARN", "deltas": {"handshake_p95_percent": 12}, "metrics": {"handshake_success_rate": 0.98}},
            {"status": "FAIL", "deltas": {"handshake_p95_percent": 40}, "metrics": {"handshake_success_rate": 0.96}},
        ]
    )

    assert summary["overall_status"] == "FAIL"
    assert summary["by_status"] == {"PASS": 1, "WARN": 1, "FAIL": 1, "ERROR": 0}
    assert summary["average_deltas"]["handshake_p95_percent"] == 18.67
    assert summary["average_metrics"]["handshake_success_rate"] == 0.98


def test_performance_engine_summarizes_latency_before_after_comparison():
    summary = summarize_results(
        [
            {
                "status": "WARN",
                "deltas": {"handshake_p95_percent": 25.0},
                "metrics": {
                    "handshake_ms": {"p95": 125},
                    "ttfb_ms": {"p95": 212},
                    "baseline_metrics": {
                        "handshake_ms": {"p95": 100},
                        "ttfb_ms": {"p95": 200},
                    },
                },
            }
        ]
    )

    assert summary["latency_comparison"]["handshake_ms"] == {
        "baseline_p95": 100.0,
        "candidate_p95": 125.0,
        "delta_percent": 25.0,
    }
    assert summary["latency_comparison"]["ttfb_ms"]["delta_percent"] == 6.0


def test_performance_engine_flags_throughput_drop_and_summarizes_before_after_comparison():
    result = evaluate_asset_performance(
        metrics={"throughput_rps": 650.0},
        baseline_metrics={"throughput_rps": 1000.0},
        compatibility_status="PASS",
    )
    summary = summarize_results(
        [
            {
                "status": result["status"],
                "deltas": result["deltas"],
                "metrics": {
                    "throughput_rps": 650.0,
                    "baseline_metrics": {"throughput_rps": 1000.0},
                },
            }
        ]
    )

    assert result["status"] == "FAIL"
    assert result["deltas"]["throughput_rps_percent"] == -35.0
    assert any(signal["reason"] == "throughput_rps_percent_below_fail_threshold" for signal in result["signals"])
    assert summary["average_metrics"]["throughput_rps"] == 650.0
    assert summary["throughput_comparison"]["throughput_rps"] == {
        "baseline_value": 1000.0,
        "candidate_value": 650.0,
        "delta_percent": -35.0,
    }


def test_performance_engine_normalizes_tls_handshake_success_rate_and_flags_regression():
    metrics = normalize_availability_metrics({"successful_handshakes": 98, "failed_handshakes": 2})

    result = evaluate_asset_performance(metrics=metrics, compatibility_status="PASS")

    assert metrics["total_handshakes"] == 100
    assert metrics["handshake_success_rate"] == 0.98
    assert metrics["failure_rate"] == 0.02
    assert result["status"] == "WARN"
    assert any(signal["reason"] == "handshake_success_rate_below_warn_threshold" for signal in result["signals"])


def test_performance_engine_summarizes_ssh_handshake_success_rate_by_protocol():
    summary = summarize_results(
        [
            {"status": "PASS", "deltas": {}, "metrics": normalize_availability_metrics({"protocol": "SSH", "successful_handshakes": 10})},
            {
                "status": "WARN",
                "deltas": {},
                "metrics": normalize_availability_metrics({"protocol": "SSH", "successful_handshakes": 19, "failed_handshakes": 1}),
            },
            {"status": "PASS", "deltas": {}, "metrics": normalize_availability_metrics({"protocol": "TLS", "failure_rate": 0.0})},
        ]
    )

    assert summary["by_protocol"]["SSH"]["total_results"] == 2
    assert summary["by_protocol"]["SSH"]["by_status"]["WARN"] == 1
    assert summary["by_protocol"]["SSH"]["average_metrics"]["handshake_success_rate"] == 0.975
    assert summary["by_protocol"]["TLS"]["average_metrics"]["handshake_success_rate"] == 1.0


def test_performance_engine_normalizes_ike_negotiation_success_rate_by_protocol():
    metrics = normalize_availability_metrics({"protocol": "IKE", "successful_negotiations": 9, "failed_negotiations": 1})

    result = evaluate_asset_performance(metrics=metrics, compatibility_status="PASS")
    summary = summarize_results([{"status": result["status"], "deltas": result["deltas"], "metrics": metrics}])

    assert metrics["total_negotiations"] == 10
    assert metrics["negotiation_success_rate"] == 0.9
    assert metrics["availability_success_rate"] == 0.9
    assert result["status"] == "FAIL"
    assert any(signal["reason"] == "negotiation_success_rate_below_fail_threshold" for signal in result["signals"])
    assert summary["by_protocol"]["IKE"]["average_metrics"]["negotiation_success_rate"] == 0.9


def test_performance_engine_summarizes_protocol_response_codes_and_failure_reasons():
    metrics = normalize_availability_metrics(
        {
            "protocol": "TLS",
            "response_code": "tls_alert_bad_certificate",
            "failure_reason": "certificate_verify_failed",
            "failure_rate": 1.0,
        }
    )
    summary = summarize_results([{"status": "FAIL", "deltas": {}, "metrics": metrics}])

    assert metrics["response_code"] == "tls_alert_bad_certificate"
    assert metrics["failure_reason"] == "certificate_verify_failed"
    assert summary["by_protocol"]["TLS"]["response_codes"] == {"tls_alert_bad_certificate": 1}
    assert summary["by_protocol"]["TLS"]["failure_reasons"] == {"certificate_verify_failed": 1}


def test_performance_engine_flags_legacy_client_compatibility_failure():
    metrics = normalize_availability_metrics(
        {
            "protocol": "TLS",
            "client_compatibility": [
                {"profile": "modern_tls13", "status": "PASS", "response_code": "tls_ok"},
                {
                    "profile": "legacy_tls12",
                    "status": "FAIL",
                    "response_code": "handshake_failure",
                    "failure_reason": "unsupported_signature_algorithm",
                },
            ],
        }
    )

    result = evaluate_asset_performance(metrics=metrics, compatibility_status="PASS")
    summary = summarize_results([{"status": result["status"], "deltas": result["deltas"], "metrics": metrics}])

    assert result["status"] == "FAIL"
    assert any(signal["reason"] == "client_legacy_tls12_compatibility_failed" for signal in result["signals"])
    assert metrics["client_compatibility"][1]["failure_reason"] == "unsupported_signature_algorithm"
    assert summary["client_compatibility"]["total_checks"] == 2
    assert summary["client_compatibility"]["by_status"] == {"PASS": 1, "WARN": 0, "FAIL": 1, "ERROR": 0}
    assert summary["client_compatibility"]["by_profile"]["legacy_tls12"]["overall_status"] == "FAIL"
    assert summary["client_compatibility"]["by_profile"]["legacy_tls12"]["failure_reasons"] == {"unsupported_signature_algorithm": 1}
    assert {
        "protocol": "TLS",
        "client_profile": "legacy_tls12",
        "response_code": "handshake_failure",
        "failure_reason": "unsupported_signature_algorithm",
        "count": 1,
        "asset_refs": ["-"],
        "status": "FAIL",
    } in summary["failure_paths"]
