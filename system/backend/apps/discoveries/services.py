import os
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from ipaddress import ip_address, ip_network

from django.db import transaction
from django.utils import timezone

from apps.discoveries import agent_client
from apps.jobs.models import AsyncJob, QueuedTask
from apps.jobs.services import enqueue_task, serialize_dt, serialize_job


class EnqueueUnavailable(Exception):
    pass


DEFAULT_DISCOVERY_PORTS = [
    22,
    25,
    443,
    465,
    500,
    587,
    993,
    995,
    2222,
    3306,
    4500,
    5000,
    5432,
    6380,
    8200,
    8443,
    8883,
    9090,
    9093,
    9200,
    9443,
    15017,
]


def enqueue_discovery(discovery) -> None:
    scope_value = discovery.scope_value or discovery.cidr
    discovery_agent_id = str(discovery.discovery_agent_id) if discovery.discovery_agent_id else None
    enqueue_task(
        "discovery",
        {
            "discovery_id": discovery.id,
            "scope_type": discovery.scope_type,
            "scope_value": scope_value,
            "cidr": discovery.cidr,
            "executor_type": discovery.executor_type,
            "agent_id": discovery_agent_id,
            "ports": discovery.ports,
        },
        async_job=discovery.async_job,
    )


def serialize_discovery(discovery):
    scope_value = discovery.scope_value or discovery.cidr
    result = discovery.async_job.result or {}
    return {
        "id": discovery.id,
        "job_id": discovery.async_job_id,
        "status": discovery.status,
        "progress": discovery.async_job.progress,
        "scope_type": discovery.scope_type,
        "scope_value": scope_value,
        "cidr": discovery.cidr,
        "executor_type": discovery.executor_type,
        "agent_id": str(discovery.discovery_agent_id) if discovery.discovery_agent_id else None,
        "agent_hostname": discovery.discovery_agent.hostname if discovery.discovery_agent_id else None,
        "port_list": discovery.ports,
        "ports": discovery.ports,
        "include_default_ports": discovery.include_default_ports,
        "created_at": serialize_dt(discovery.created_at),
        "started_at": serialize_dt(discovery.started_at),
        "finished_at": serialize_dt(discovery.finished_at),
        "error": discovery.error,
        "availability_report": result.get("availability_report") or result.get("performance_report"),
    }


def serialize_endpoint(endpoint):
    return {
        "id": endpoint.id,
        "ip": endpoint.host,
        "host": endpoint.host,
        "port": endpoint.port,
        "transport": endpoint.transport,
        "detected_protocol": endpoint.detected_protocol,
        "banner_metadata": {},
        "suggested_protocol_hint": endpoint.suggested_protocol_hint,
        "suggested_host": endpoint.host,
        "promoted": endpoint.promoted,
        "target_id": endpoint.target_id,
        "availability_metrics": endpoint.availability_metrics,
    }


def discovery_job_envelope(discovery):
    return serialize_job(discovery.async_job)


def resolved_ports(discovery_or_payload) -> list[int]:
    if isinstance(discovery_or_payload, dict):
        include_default_ports = bool(discovery_or_payload.get("include_default_ports", False))
        ports = list(discovery_or_payload.get("ports", []) or [])
    else:
        include_default_ports = bool(getattr(discovery_or_payload, "include_default_ports", False))
        ports = list(getattr(discovery_or_payload, "ports", []) or [])
    if include_default_ports:
        ports = [*ports, *DEFAULT_DISCOVERY_PORTS]
    return sorted({int(port) for port in ports})


def process_next_discovery_task() -> dict | None:
    task = (
        QueuedTask.objects.filter(task_name="discovery", status=QueuedTask.QUEUED, available_at__lte=timezone.now())
        .order_by("available_at", "id")
        .first()
    )
    if not task:
        return None
    return process_discovery_task(task.id)


def process_discovery_task(task_id: int) -> dict:
    from apps.discoveries.models import Discovery

    with transaction.atomic():
        task = QueuedTask.objects.select_for_update().select_related("async_job").get(id=task_id)
        if task.status == QueuedTask.CANCELLED:
            return {}
        if task.status != QueuedTask.QUEUED:
            raise ValueError(f"QueuedTask {task.id} is not queued")
        async_job = task.async_job
        discovery = Discovery.objects.select_for_update().select_related("discovery_agent").get(id=task.payload["discovery_id"])
        now = timezone.now()
        task.status = QueuedTask.RUNNING
        task.attempts += 1
        task.locked_at = now
        task.save(update_fields=["status", "attempts", "locked_at", "updated_at"])
        if async_job:
            if async_job.status == AsyncJob.CANCELLED:
                task.status = QueuedTask.CANCELLED
                task.save(update_fields=["status", "updated_at"])
                return {}
            async_job.status = AsyncJob.RUNNING
            async_job.started_at = async_job.started_at or now
            async_job.progress = {"current": 0, "total": None, "percent": 0}
            async_job.save(update_fields=["status", "started_at", "progress", "updated_at"])
        discovery.status = AsyncJob.RUNNING
        discovery.started_at = discovery.started_at or now
        discovery.error = None
        discovery.save(update_fields=["status", "started_at", "error", "updated_at"])

    try:
        result = run_discovery_payload(task.payload)
    except Exception as exc:
        _fail_discovery_task(task_id, exc)
        raise

    _complete_discovery_task(task_id, result)
    return result


def run_discovery_payload(payload: dict) -> dict:
    from apps.discoveries.models import Discovery

    discovery = Discovery.objects.select_related("discovery_agent").get(id=payload["discovery_id"])
    ports = resolved_ports(discovery)
    request_payload = {
        "scope_type": discovery.scope_type,
        "scope_value": discovery.scope_value or discovery.cidr,
        "cidr": discovery.cidr,
        "ports": ports,
    }
    if discovery.executor_type == "agent":
        response = agent_client.post_discover(discovery.discovery_agent, request_payload)
        endpoints = response.get("endpoints", [])
        availability_report = response.get("availability_report") or response.get("performance_report")
    else:
        endpoints = central_discover(request_payload)
        availability_report = None

    saved_count = upsert_discovered_endpoints(discovery, endpoints)
    availability_report = availability_report or summarize_discovery_availability(endpoints)
    return {
        "discovery_id": discovery.id,
        "executor_type": discovery.executor_type,
        "endpoints_count": saved_count,
        "availability_report": availability_report,
    }


def upsert_discovered_endpoints(discovery, endpoints: list[dict]) -> int:
    from apps.discoveries.models import DiscoveredEndpoint

    saved = 0
    for endpoint in endpoints:
        host = str(endpoint.get("host") or endpoint.get("ip") or "").strip()
        port = int(endpoint.get("port") or 0)
        transport = str(endpoint.get("transport") or "TCP").upper()
        if not host or port < 1 or port > 65535 or transport not in {"TCP", "UDP"}:
            continue
        detected_protocol = str(endpoint.get("detected_protocol") or "UNKNOWN")[:32]
        suggested_protocol_hint = str(endpoint.get("suggested_protocol_hint") or _protocol_hint_for_port(port, transport))[:16]
        availability_metrics = _endpoint_availability_metrics(endpoint)
        existing = (
            DiscoveredEndpoint.objects.filter(discovery=discovery, host=host, port=port, transport=transport)
            .order_by("id")
            .first()
        )
        if existing:
            existing.detected_protocol = detected_protocol
            existing.suggested_protocol_hint = suggested_protocol_hint
            existing.availability_metrics = availability_metrics
            existing.save(update_fields=["detected_protocol", "suggested_protocol_hint", "availability_metrics"])
            DiscoveredEndpoint.objects.filter(discovery=discovery, host=host, port=port, transport=transport).exclude(id=existing.id).delete()
            _auto_promote_endpoint(existing)
        else:
            created = DiscoveredEndpoint.objects.create(
                discovery=discovery,
                host=host,
                port=port,
                transport=transport,
                detected_protocol=detected_protocol,
                suggested_protocol_hint=suggested_protocol_hint,
                availability_metrics=availability_metrics,
            )
            _auto_promote_endpoint(created)
        saved += 1
    return saved


def _auto_promote_endpoint(endpoint) -> None:
    from apps.targets.models import Target, default_context

    protocol_hint = _normalized_protocol_hint(endpoint.suggested_protocol_hint)
    target, _created = Target.objects.get_or_create(
        host=endpoint.host,
        port=endpoint.port,
        transport=endpoint.transport,
        defaults={
            "ip": _ip_or_none(endpoint.host),
            "protocol_hint": protocol_hint,
            "context": default_context(),
            "agent_enabled": False,
        },
    )
    update_fields = []
    if endpoint.target_id != target.id:
        endpoint.target = target
        update_fields.append("target")
    if not endpoint.promoted:
        endpoint.promoted = True
        update_fields.append("promoted")
    if update_fields:
        endpoint.save(update_fields=update_fields)


def _normalized_protocol_hint(value: str) -> str:
    normalized = str(value or "UNKNOWN").upper()
    return normalized if normalized in {"TLS", "SSH", "IKE", "SMTP", "IMAP", "POP3", "UNKNOWN"} else "UNKNOWN"


def _ip_or_none(host: str) -> str | None:
    try:
        return str(ip_address(host))
    except ValueError:
        return None


def summarize_discovery_availability(endpoints: list[dict]) -> dict:
    metrics = [
        metric
        for endpoint in endpoints
        if isinstance((metric := _endpoint_availability_metrics(endpoint)), dict) and metric
    ]
    tls_endpoint_count = len(
        [
            endpoint
            for endpoint in endpoints
            if str(endpoint.get("transport") or "TCP").upper() == "TCP"
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


def _endpoint_availability_metrics(endpoint: dict) -> dict:
    metrics = endpoint.get("availability_metrics") or endpoint.get("performance_metrics") or endpoint.get("performance") or {}
    return metrics if isinstance(metrics, dict) else {}


def _series_samples(metrics: dict, key: str) -> int:
    series = metrics.get(key)
    if isinstance(series, dict):
        value = series.get("samples")
        if isinstance(value, int):
            return value
    sample_count = metrics.get("sample_count")
    return sample_count if isinstance(sample_count, int) else 0


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


def central_discover(payload: dict) -> list[dict]:
    scope_type = payload.get("scope_type", "cidr")
    scope_value = payload.get("scope_value") or payload.get("cidr") or ""
    hosts = _hosts_for_scope(scope_type, scope_value)
    ports = [int(port) for port in payload.get("ports", [])]
    tcp_candidates = [(host, port) for host in hosts for port in ports if port not in {500, 4500}]
    if not tcp_candidates:
        return []

    endpoints = []
    max_workers = int(os.getenv("DISCOVERY_CENTRAL_MAX_WORKERS", "128"))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_tcp_port_open, host, port): (host, port) for host, port in tcp_candidates}
        for future in as_completed(futures):
            host, port = futures[future]
            if not future.result():
                continue
            endpoints.append(
                {
                    "host": host,
                    "port": port,
                    "transport": "TCP",
                    "detected_protocol": _protocol_hint_for_port(port, "TCP"),
                    "suggested_protocol_hint": _protocol_hint_for_port(port, "TCP"),
                }
            )
    return endpoints


def _hosts_for_scope(scope_type: str, scope_value: str) -> list[str]:
    value = str(scope_value).strip()
    if not value:
        return []
    if scope_type == "cidr":
        network = ip_network(value, strict=False)
        return [str(host) for host in network.hosts()]
    if scope_type == "ip":
        return [str(ip_address(value))]
    return [value]


def _tcp_port_open(host: str, port: int, timeout_sec: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True
    except OSError:
        return False


def _protocol_hint_for_port(port: int, transport: str) -> str:
    if transport == "UDP" and port in {500, 4500}:
        return "IKE"
    if port in {22, 2222}:
        return "SSH"
    if port in {25, 465, 587}:
        return "SMTP"
    if port == 993:
        return "IMAP"
    if port == 995:
        return "POP3"
    if port in {443, 8443, 8883, 9093, 9443, 15017, 3306, 5000, 5432, 6380, 8200, 9090, 9200}:
        return "TLS"
    return "UNKNOWN"


def _complete_discovery_task(task_id: int, result: dict) -> None:
    from apps.discoveries.models import Discovery

    with transaction.atomic():
        task = QueuedTask.objects.select_for_update().select_related("async_job").get(id=task_id)
        try:
            discovery = Discovery.objects.select_for_update().get(id=task.payload["discovery_id"])
        except Discovery.DoesNotExist:
            discovery = None
        if task.async_job and task.async_job.status == AsyncJob.CANCELLED:
            task.status = QueuedTask.CANCELLED
            task.save(update_fields=["status", "updated_at"])
            return
        task.status = QueuedTask.COMPLETED
        task.last_error = None
        task.save(update_fields=["status", "last_error", "updated_at"])
        now = timezone.now()
        if discovery:
            discovery.status = AsyncJob.COMPLETED
            discovery.finished_at = now
            discovery.error = None
            discovery.save(update_fields=["status", "finished_at", "error", "updated_at"])
        if task.async_job:
            async_job = task.async_job
            async_job.status = AsyncJob.COMPLETED
            async_job.progress = {"current": result.get("endpoints_count", 0), "total": result.get("endpoints_count", 0), "percent": 100}
            async_job.result = result
            async_job.error = None
            async_job.finished_at = now
            async_job.save(update_fields=["status", "progress", "result", "error", "finished_at", "updated_at"])


def _fail_discovery_task(task_id: int, exc: Exception) -> None:
    from apps.discoveries.models import Discovery

    with transaction.atomic():
        task = QueuedTask.objects.select_for_update().select_related("async_job").get(id=task_id)
        task.status = QueuedTask.FAILED
        task.last_error = str(exc)
        task.save(update_fields=["status", "last_error", "updated_at"])
        now = timezone.now()
        try:
            discovery = Discovery.objects.select_for_update().get(id=task.payload["discovery_id"])
        except Discovery.DoesNotExist:
            discovery = None
        if discovery:
            discovery.status = AsyncJob.FAILED
            discovery.error = str(exc)[:255]
            discovery.finished_at = now
            discovery.save(update_fields=["status", "error", "finished_at", "updated_at"])
        if task.async_job:
            async_job = task.async_job
            async_job.status = AsyncJob.FAILED
            async_job.error = {"message": str(exc)}
            async_job.finished_at = now
            async_job.save(update_fields=["status", "error", "finished_at", "updated_at"])
