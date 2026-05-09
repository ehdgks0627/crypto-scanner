import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from ipaddress import ip_address, ip_network

from .registry import build_default_registry


def discover(payload: dict) -> dict:
    endpoints = discover_endpoints(payload)
    return {
        "endpoints": endpoints,
        "availability_report": summarize_availability(endpoints),
    }


def discover_endpoints(payload: dict) -> list[dict]:
    ports = sorted({int(port) for port in payload.get("ports", []) if 1 <= int(port) <= 65535})
    hosts = _hosts_for_scope(
        str(payload.get("scope_type") or "cidr"),
        str(payload.get("scope_value") or payload.get("cidr") or ""),
    )
    if not ports or not hosts:
        return []

    timeout_sec = float(os.getenv("DISCOVERY_PROBE_TIMEOUT_SEC", "0.45"))
    max_workers = int(os.getenv("DISCOVERY_MAX_WORKERS", "128"))
    registry = build_default_registry()
    endpoints = []
    seen = set()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_probe_host_port, registry, host, port, _transport_for_port(port), timeout_sec)
            for host in hosts
            for port in ports
        ]
        for future in as_completed(futures):
            endpoint = future.result()
            if endpoint is None:
                continue
            key = (endpoint.host, endpoint.port, endpoint.transport)
            if key in seen:
                continue
            seen.add(key)
            endpoints.append(endpoint.as_dict())

    return sorted(endpoints, key=lambda item: (_host_sort_key(item["host"]), item["port"], item["transport"]))


def summarize_availability(endpoints: list[dict]) -> dict:
    metrics = [
        metrics
        for endpoint in endpoints
        if isinstance((metrics := endpoint.get("availability_metrics") or endpoint.get("performance_metrics")), dict) and metrics
    ]
    tls_endpoint_count = len(
        [
            endpoint
            for endpoint in endpoints
            if endpoint.get("transport") == "TCP"
            and str(endpoint.get("suggested_protocol_hint") or endpoint.get("detected_protocol") or "").upper() == "TLS"
        ]
    )
    if not metrics:
        return {
            "measured_endpoint_count": 0,
            "tls_endpoint_count": tls_endpoint_count,
            "sample_count": 0,
            "averages": {},
            "max": {},
            "rates": {"failure_rate": 0.0, "timeout_rate": 0.0},
        }
    return {
        "measured_endpoint_count": len(metrics),
        "tls_endpoint_count": tls_endpoint_count,
        "sample_count": int(sum(_series_samples(metric, "handshake_ms") for metric in metrics)),
        "averages": {
            "tcp_connect_p95_ms": _average_metric(metrics, "tcp_connect_ms", "p95"),
            "handshake_p95_ms": _average_metric(metrics, "handshake_ms", "p95"),
            "ttfb_p95_ms": _average_metric(metrics, "ttfb_ms", "p95"),
            "total_request_p95_ms": _average_metric(metrics, "total_request_ms", "p95"),
        },
        "max": {
            "tcp_connect_p95_ms": _max_metric(metrics, "tcp_connect_ms", "p95"),
            "handshake_p95_ms": _max_metric(metrics, "handshake_ms", "p95"),
            "ttfb_p95_ms": _max_metric(metrics, "ttfb_ms", "p95"),
            "total_request_p95_ms": _max_metric(metrics, "total_request_ms", "p95"),
        },
        "rates": {
            "failure_rate": _average_scalar(metrics, "failure_rate"),
            "timeout_rate": _average_scalar(metrics, "timeout_rate"),
        },
        "handshake_bytes": {
            "sent": _average_scalar(metrics, "handshake_bytes_sent"),
            "received": _average_scalar(metrics, "handshake_bytes_received"),
        },
    }


def _probe_host_port(registry, host: str, port: int, transport: str, timeout_sec: float):
    for probe in registry.probes_for(port, transport):
        endpoint = probe.run(host, port, timeout_sec)
        if endpoint is not None:
            return endpoint
    return None


def _hosts_for_scope(scope_type: str, scope_value: str) -> list[str]:
    value = scope_value.strip()
    if not value:
        return []
    if scope_type == "cidr":
        max_hosts = int(os.getenv("DISCOVERY_MAX_HOSTS", "4096"))
        network = ip_network(value, strict=False)
        return [str(host) for index, host in enumerate(network.hosts()) if index < max_hosts]
    if scope_type == "ip":
        return [str(ip_address(value))]
    return [value.rstrip(".").lower()]


def _transport_for_port(port: int) -> str:
    return "UDP" if port in {500, 4500} else "TCP"


def _host_sort_key(host: str):
    try:
        return (0, int(ip_address(host)))
    except ValueError:
        return (1, host)


def _series_samples(metrics: dict, key: str) -> int:
    series = metrics.get(key)
    if isinstance(series, dict) and isinstance(series.get("samples"), int):
        return series["samples"]
    return int(metrics.get("sample_count") or 0)


def _series_value(metrics: dict, key: str, percentile: str) -> float | None:
    series = metrics.get(key)
    if isinstance(series, dict):
        return _number(series.get(percentile))
    return _number(series)


def _average_metric(metrics: list[dict], key: str, percentile: str) -> float | None:
    return _average([_series_value(metric, key, percentile) for metric in metrics])


def _max_metric(metrics: list[dict], key: str, percentile: str) -> float | None:
    values = [value for metric in metrics if (value := _series_value(metric, key, percentile)) is not None]
    return round(max(values), 2) if values else None


def _average_scalar(metrics: list[dict], key: str) -> float | None:
    return _average([_number(metric.get(key)) for metric in metrics])


def _average(values: list[float | None]) -> float | None:
    numeric = [value for value in values if value is not None]
    return round(sum(numeric) / len(numeric), 4) if numeric else None


def _number(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None
