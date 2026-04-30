from performance_engine import evaluate_asset_performance, summarize_results


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
            {"status": "PASS", "deltas": {"handshake_p95_percent": 4}},
            {"status": "WARN", "deltas": {"handshake_p95_percent": 12}},
            {"status": "FAIL", "deltas": {"handshake_p95_percent": 40}},
        ]
    )

    assert summary["overall_status"] == "FAIL"
    assert summary["by_status"] == {"PASS": 1, "WARN": 1, "FAIL": 1, "ERROR": 0}
    assert summary["average_deltas"]["handshake_p95_percent"] == 18.67
