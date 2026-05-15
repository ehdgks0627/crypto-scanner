from __future__ import annotations

from typing import Any


DEFAULT_THRESHOLDS = {
    "warn_latency_delta_percent": 10.0,
    "fail_latency_delta_percent": 30.0,
    "warn_failure_rate": 0.01,
    "fail_failure_rate": 0.03,
    "warn_handshake_success_rate": 0.99,
    "fail_handshake_success_rate": 0.97,
    "warn_timeout_rate": 0.01,
    "fail_timeout_rate": 0.03,
    "warn_handshake_bytes_delta_percent": 50.0,
    "fail_handshake_bytes_delta_percent": 100.0,
}

LATENCY_SERIES = ("tcp_connect_ms", "handshake_ms", "ttfb_ms", "total_request_ms")


def evaluate_asset_performance(
    *,
    metrics: dict[str, Any],
    baseline_metrics: dict[str, Any] | None = None,
    compatibility_status: str = "PASS",
    thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged_thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    metrics = normalize_availability_metrics(metrics)
    baseline_metrics = normalize_availability_metrics(baseline_metrics or {})
    deltas = _calculate_deltas(metrics, baseline_metrics or {})
    signals = _collect_signals(metrics, deltas, compatibility_status, merged_thresholds)
    status = _status_from_signals(signals)
    return {
        "status": status,
        "deltas": deltas,
        "recommendation": _recommendation_for(status, compatibility_status),
        "signals": signals,
    }


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0, "ERROR": 0}
    for result in results:
        status = result.get("status")
        if status in counts:
            counts[status] += 1

    completed_count = sum(counts.values())
    average_deltas = {}
    delta_keys = sorted({key for result in results for key in (result.get("deltas") or {})})
    for key in delta_keys:
        values = [
            value
            for result in results
            if isinstance((value := (result.get("deltas") or {}).get(key)), (int, float))
        ]
        if values:
            average_deltas[key] = round(sum(values) / len(values), 2)

    average_metrics = {}
    for key in ("availability_success_rate", "handshake_success_rate", "negotiation_success_rate", "failure_rate", "timeout_rate"):
        values = [
            value
            for result in results
            if isinstance((value := (result.get("metrics") or {}).get(key)), (int, float))
        ]
        if values:
            average_metrics[key] = round(sum(values) / len(values), 4)

    return {
        "total_results": completed_count,
        "by_status": counts,
        "average_deltas": average_deltas,
        "average_metrics": average_metrics,
        "by_protocol": _summarize_by_protocol(results),
        "overall_status": _overall_status(counts),
    }


def normalize_availability_metrics(metrics: dict[str, Any] | None) -> dict[str, Any]:
    normalized = dict(metrics or {})
    if normalized.get("protocol"):
        normalized["protocol"] = str(normalized["protocol"]).upper()
    success_key = _success_rate_key(normalized)
    success = _number(normalized.get("successful_handshakes"))
    failed = _number(normalized.get("failed_handshakes"))
    total = _number(normalized.get("total_handshakes")) or _number(normalized.get("attempted_handshakes"))
    if success is None:
        success = _number(normalized.get("successful_negotiations"))
        failed = _number(normalized.get("failed_negotiations"))
        total = _number(normalized.get("total_negotiations")) or _number(normalized.get("attempted_negotiations"))

    if total is None and success is not None:
        total = success + (failed or 0.0)
    if total and total > 0 and success is not None:
        success_rate = _clamp_rate(success / total)
        normalized[success_key] = round(success_rate, 4)
        normalized["availability_success_rate"] = round(success_rate, 4)
        normalized.setdefault("failure_rate", round(_clamp_rate(1 - success_rate), 4))
        total_key = "total_negotiations" if success_key == "negotiation_success_rate" else "total_handshakes"
        normalized.setdefault(total_key, int(total) if total.is_integer() else total)
    elif "availability_success_rate" not in normalized:
        failure_rate = _number(normalized.get("failure_rate"))
        if failure_rate is not None:
            success_rate = round(_clamp_rate(1 - failure_rate), 4)
            normalized["availability_success_rate"] = success_rate
            normalized.setdefault(success_key, success_rate)
    elif success_key not in normalized:
        normalized[success_key] = normalized["availability_success_rate"]
    if "availability_success_rate" not in normalized:
        direct_success_rate = _number(normalized.get(success_key))
        if direct_success_rate is not None:
            normalized["availability_success_rate"] = round(_clamp_rate(direct_success_rate), 4)
    return normalized


def _summarize_by_protocol(results: list[dict[str, Any]]) -> dict[str, Any]:
    protocols: dict[str, dict[str, Any]] = {}
    for result in results:
        metrics = result.get("metrics") or {}
        protocol = str(metrics.get("protocol") or "UNKNOWN").upper()
        entry = protocols.setdefault(
            protocol,
            {
                "total_results": 0,
                "by_status": {"PASS": 0, "WARN": 0, "FAIL": 0, "ERROR": 0},
                "_metrics": {
                    "availability_success_rate": [],
                    "handshake_success_rate": [],
                    "negotiation_success_rate": [],
                    "failure_rate": [],
                    "timeout_rate": [],
                },
            },
        )
        entry["total_results"] += 1
        status = result.get("status")
        if status in entry["by_status"]:
            entry["by_status"][status] += 1
        for key, values in entry["_metrics"].items():
            value = metrics.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values.append(value)

    summary = {}
    for protocol, entry in protocols.items():
        average_metrics = {
            key: round(sum(values) / len(values), 4)
            for key, values in entry["_metrics"].items()
            if values
        }
        summary[protocol] = {
            "total_results": entry["total_results"],
            "by_status": entry["by_status"],
            "average_metrics": average_metrics,
        }
    return summary


def _calculate_deltas(metrics: dict[str, Any], baseline_metrics: dict[str, Any]) -> dict[str, float]:
    deltas: dict[str, float] = {}
    for series in LATENCY_SERIES:
        delta = _percent_delta(_metric_value(metrics, series, "p95"), _metric_value(baseline_metrics, series, "p95"))
        if delta is not None:
            deltas[f"{series.removesuffix('_ms')}_p95_percent"] = delta

    candidate_bytes = _handshake_bytes(metrics)
    baseline_bytes = _handshake_bytes(baseline_metrics)
    bytes_delta = _percent_delta(candidate_bytes, baseline_bytes)
    if bytes_delta is not None:
        deltas["handshake_bytes_percent"] = bytes_delta
    return deltas


def _collect_signals(metrics: dict[str, Any], deltas: dict[str, float], compatibility_status: str, thresholds: dict[str, Any]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    if compatibility_status in {"FAIL", "ERROR"}:
        signals.append({"level": "FAIL", "reason": "compatibility_failed"})
    elif compatibility_status == "WARN":
        signals.append({"level": "WARN", "reason": "compatibility_warning"})

    failure_rate = _number(metrics.get("failure_rate"), 0.0)
    timeout_rate = _number(metrics.get("timeout_rate"), 0.0)
    success_metric = _success_rate_key(metrics)
    success_rate = _number(metrics.get(success_metric))
    if success_rate is None:
        success_metric = "availability_success_rate"
        success_rate = _number(metrics.get(success_metric))
    if success_rate is not None:
        _append_min_rate_signal(
            signals,
            success_metric,
            success_rate,
            thresholds["warn_handshake_success_rate"],
            thresholds["fail_handshake_success_rate"],
        )
    _append_rate_signal(signals, "failure_rate", failure_rate, thresholds["warn_failure_rate"], thresholds["fail_failure_rate"])
    _append_rate_signal(signals, "timeout_rate", timeout_rate, thresholds["warn_timeout_rate"], thresholds["fail_timeout_rate"])

    for key, delta in deltas.items():
        if key == "handshake_bytes_percent":
            warn = thresholds["warn_handshake_bytes_delta_percent"]
            fail = thresholds["fail_handshake_bytes_delta_percent"]
        else:
            warn = thresholds["warn_latency_delta_percent"]
            fail = thresholds["fail_latency_delta_percent"]
        if delta > fail:
            signals.append({"level": "FAIL", "reason": f"{key}_above_fail_threshold", "value": delta})
        elif delta > warn:
            signals.append({"level": "WARN", "reason": f"{key}_above_warn_threshold", "value": delta})
    return signals


def _append_rate_signal(signals: list[dict[str, Any]], key: str, value: float, warn: float, fail: float) -> None:
    if value > fail:
        signals.append({"level": "FAIL", "reason": f"{key}_above_fail_threshold", "value": value})
    elif value > warn:
        signals.append({"level": "WARN", "reason": f"{key}_above_warn_threshold", "value": value})


def _append_min_rate_signal(signals: list[dict[str, Any]], key: str, value: float, warn: float, fail: float) -> None:
    if value < fail:
        signals.append({"level": "FAIL", "reason": f"{key}_below_fail_threshold", "value": value})
    elif value < warn:
        signals.append({"level": "WARN", "reason": f"{key}_below_warn_threshold", "value": value})


def _success_rate_key(metrics: dict[str, Any]) -> str:
    protocol = str(metrics.get("protocol") or "").upper()
    return "negotiation_success_rate" if protocol == "IKE" else "handshake_success_rate"


def _status_from_signals(signals: list[dict[str, Any]]) -> str:
    levels = {signal["level"] for signal in signals}
    if "FAIL" in levels:
        return "FAIL"
    if "WARN" in levels:
        return "WARN"
    return "PASS"


def _recommendation_for(status: str, compatibility_status: str) -> str:
    if compatibility_status == "ERROR":
        return "manual_review"
    if status == "FAIL":
        return "rollback_or_manual_review"
    if status == "WARN":
        return "canary_more"
    return "proceed"


def _overall_status(counts: dict[str, int]) -> str:
    if counts["ERROR"]:
        return "ERROR"
    if counts["FAIL"]:
        return "FAIL"
    if counts["WARN"]:
        return "WARN"
    if counts["PASS"]:
        return "PASS"
    return "PENDING"


def _metric_value(metrics: dict[str, Any], series: str, percentile: str) -> float | None:
    value = metrics.get(series)
    if isinstance(value, dict):
        return _number(value.get(percentile))
    return _number(value)


def _handshake_bytes(metrics: dict[str, Any]) -> float | None:
    sent = _number(metrics.get("handshake_bytes_sent"))
    received = _number(metrics.get("handshake_bytes_received"))
    if sent is None and received is None:
        return None
    return (sent or 0.0) + (received or 0.0)


def _percent_delta(candidate: float | None, baseline: float | None) -> float | None:
    if candidate is None or baseline is None or baseline <= 0:
        return None
    return round(((candidate - baseline) / baseline) * 100, 2)


def _clamp_rate(value: float) -> float:
    return max(0.0, min(1.0, value))


def _number(value: Any, default: float | None = None) -> float | None:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default
