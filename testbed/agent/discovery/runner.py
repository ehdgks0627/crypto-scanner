import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from ipaddress import ip_address, ip_network

from .registry import build_default_registry


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
