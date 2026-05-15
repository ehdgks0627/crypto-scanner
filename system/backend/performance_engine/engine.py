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
    "warn_throughput_drop_percent": 10.0,
    "fail_throughput_drop_percent": 30.0,
}

LATENCY_SERIES = ("tcp_connect_ms", "handshake_ms", "ttfb_ms", "total_request_ms")
THROUGHPUT_SERIES = ("throughput_rps", "requests_per_second", "connections_per_second")
THROUGHPUT_DELTA_KEYS = {f"{series}_percent" for series in THROUGHPUT_SERIES}
RESULT_STATUSES = ("PASS", "WARN", "FAIL", "ERROR")


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
    for key in (
        "availability_success_rate",
        "handshake_success_rate",
        "negotiation_success_rate",
        "failure_rate",
        "timeout_rate",
        *THROUGHPUT_SERIES,
    ):
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
        "latency_comparison": _summarize_latency_comparison(results),
        "throughput_comparison": _summarize_throughput_comparison(results),
        "client_compatibility": _summarize_client_compatibility(results),
        "by_protocol": _summarize_by_protocol(results),
        "overall_status": _overall_status(counts),
    }


def normalize_availability_metrics(metrics: dict[str, Any] | None) -> dict[str, Any]:
    normalized = dict(metrics or {})
    if normalized.get("protocol"):
        normalized["protocol"] = str(normalized["protocol"]).upper()
    _normalize_text_metric(normalized, "response_code")
    _normalize_text_metric(normalized, "failure_reason")
    client_checks = _normalize_client_compatibility(normalized.get("client_compatibility"))
    if client_checks:
        normalized["client_compatibility"] = client_checks
    else:
        normalized.pop("client_compatibility", None)
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
                    "throughput_rps": [],
                    "requests_per_second": [],
                    "connections_per_second": [],
                },
                "response_codes": {},
                "failure_reasons": {},
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
        _increment_count(entry["response_codes"], metrics.get("response_code"))
        _increment_count(entry["failure_reasons"], metrics.get("failure_reason"))

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
            "response_codes": entry["response_codes"],
            "failure_reasons": entry["failure_reasons"],
        }
    return summary


def _summarize_latency_comparison(results: list[dict[str, Any]]) -> dict[str, Any]:
    comparison = {}
    for series in LATENCY_SERIES:
        candidate_values = []
        baseline_values = []
        for result in results:
            metrics = result.get("metrics") or {}
            baseline_metrics = metrics.get("baseline_metrics") if isinstance(metrics.get("baseline_metrics"), dict) else {}
            candidate_value = _metric_value(metrics, series, "p95")
            baseline_value = _metric_value(baseline_metrics, series, "p95")
            if candidate_value is not None and baseline_value is not None:
                candidate_values.append(candidate_value)
                baseline_values.append(baseline_value)
        if not candidate_values or not baseline_values:
            continue
        candidate_p95 = round(sum(candidate_values) / len(candidate_values), 2)
        baseline_p95 = round(sum(baseline_values) / len(baseline_values), 2)
        comparison[series] = {
            "baseline_p95": baseline_p95,
            "candidate_p95": candidate_p95,
            "delta_percent": _percent_delta(candidate_p95, baseline_p95),
        }
    return comparison


def _summarize_throughput_comparison(results: list[dict[str, Any]]) -> dict[str, Any]:
    comparison = {}
    for series in THROUGHPUT_SERIES:
        candidate_values = []
        baseline_values = []
        for result in results:
            metrics = result.get("metrics") or {}
            baseline_metrics = metrics.get("baseline_metrics") if isinstance(metrics.get("baseline_metrics"), dict) else {}
            candidate_value = _number(metrics.get(series))
            baseline_value = _number(baseline_metrics.get(series))
            if candidate_value is not None and baseline_value is not None:
                candidate_values.append(candidate_value)
                baseline_values.append(baseline_value)
        if not candidate_values or not baseline_values:
            continue
        candidate_value = round(sum(candidate_values) / len(candidate_values), 2)
        baseline_value = round(sum(baseline_values) / len(baseline_values), 2)
        comparison[series] = {
            "baseline_value": baseline_value,
            "candidate_value": candidate_value,
            "delta_percent": _percent_delta(candidate_value, baseline_value),
        }
    return comparison


def _summarize_client_compatibility(results: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "total_checks": 0,
        "by_status": _status_counts(),
        "by_profile": {},
        "overall_status": "PENDING",
    }
    for result in results:
        metrics = result.get("metrics") or {}
        for check in _client_compatibility_checks(metrics):
            profile = str(check.get("profile") or "unknown")
            status = _normalize_result_status(check.get("status"), default="ERROR")
            profile_summary = summary["by_profile"].setdefault(
                profile,
                {
                    "total_checks": 0,
                    "by_status": _status_counts(),
                    "response_codes": {},
                    "failure_reasons": {},
                    "overall_status": "PENDING",
                },
            )
            summary["total_checks"] += 1
            summary["by_status"][status] += 1
            profile_summary["total_checks"] += 1
            profile_summary["by_status"][status] += 1
            _increment_count(profile_summary["response_codes"], check.get("response_code"))
            _increment_count(profile_summary["failure_reasons"], check.get("failure_reason"))

    summary["overall_status"] = _overall_status(summary["by_status"])
    for profile_summary in summary["by_profile"].values():
        profile_summary["overall_status"] = _overall_status(profile_summary["by_status"])
    return summary


def _calculate_deltas(metrics: dict[str, Any], baseline_metrics: dict[str, Any]) -> dict[str, float]:
    deltas: dict[str, float] = {}
    for series in LATENCY_SERIES:
        delta = _percent_delta(_metric_value(metrics, series, "p95"), _metric_value(baseline_metrics, series, "p95"))
        if delta is not None:
            deltas[f"{series.removesuffix('_ms')}_p95_percent"] = delta

    for series in THROUGHPUT_SERIES:
        delta = _percent_delta(_number(metrics.get(series)), _number(baseline_metrics.get(series)))
        if delta is not None:
            deltas[f"{series}_percent"] = delta

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
    for check in _client_compatibility_checks(metrics):
        profile = _reason_token(str(check.get("profile") or "unknown"))
        status = _normalize_result_status(check.get("status"), default="ERROR")
        if status in {"FAIL", "ERROR"}:
            signals.append({"level": "FAIL", "reason": f"client_{profile}_compatibility_failed"})
        elif status == "WARN":
            signals.append({"level": "WARN", "reason": f"client_{profile}_compatibility_warning"})

    for key, delta in deltas.items():
        if key in THROUGHPUT_DELTA_KEYS:
            warn = thresholds["warn_throughput_drop_percent"]
            fail = thresholds["fail_throughput_drop_percent"]
            if delta < -fail:
                signals.append({"level": "FAIL", "reason": f"{key}_below_fail_threshold", "value": delta})
            elif delta < -warn:
                signals.append({"level": "WARN", "reason": f"{key}_below_warn_threshold", "value": delta})
            continue
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


def _normalize_text_metric(metrics: dict[str, Any], key: str) -> None:
    value = metrics.get(key)
    if value is None:
        return
    normalized = str(value).strip()
    if normalized:
        metrics[key] = normalized
    else:
        metrics.pop(key, None)


def _normalize_client_compatibility(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        raw_checks = [
            {**raw, "profile": raw.get("profile") or profile} if isinstance(raw, dict) else {"profile": profile, "status": raw}
            for profile, raw in value.items()
        ]
    elif isinstance(value, list):
        raw_checks = value
    else:
        return []

    checks = []
    for raw in raw_checks:
        if not isinstance(raw, dict):
            continue
        profile = str(raw.get("profile") or raw.get("client_profile") or raw.get("name") or "").strip()
        if not profile:
            continue
        status = _normalize_result_status(raw.get("status") or raw.get("compatibility_status"), default="PASS")
        if (raw.get("status") is None and raw.get("compatibility_status") is None) and isinstance(raw.get("success"), bool):
            status = "PASS" if raw["success"] else "FAIL"
        check = {**raw, "profile": profile, "status": status}
        _normalize_text_metric(check, "response_code")
        _normalize_text_metric(check, "failure_reason")
        checks.append(check)
    return checks


def _client_compatibility_checks(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    value = metrics.get("client_compatibility")
    return value if isinstance(value, list) else []


def _normalize_result_status(value: Any, *, default: str) -> str:
    status = str(value or default).strip().upper()
    aliases = {
        "OK": "PASS",
        "SUCCESS": "PASS",
        "PASSED": "PASS",
        "PARTIAL": "WARN",
        "FAILED": "FAIL",
        "UNREACHABLE": "FAIL",
    }
    status = aliases.get(status, status)
    return status if status in RESULT_STATUSES else default


def _status_counts() -> dict[str, int]:
    return {status: 0 for status in RESULT_STATUSES}


def _reason_token(value: str) -> str:
    token = "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_")
    return token or "unknown"


def _increment_count(counts: dict[str, int], value: Any) -> None:
    if value is None:
        return
    key = str(value).strip()
    if not key:
        return
    counts[key] = counts.get(key, 0) + 1


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
