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
    else:
        endpoints = central_discover(request_payload)

    saved_count = upsert_discovered_endpoints(discovery, endpoints)
    return {
        "discovery_id": discovery.id,
        "executor_type": discovery.executor_type,
        "endpoints_count": saved_count,
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
        existing = (
            DiscoveredEndpoint.objects.filter(discovery=discovery, host=host, port=port, transport=transport)
            .order_by("id")
            .first()
        )
        if existing:
            existing.detected_protocol = detected_protocol
            existing.suggested_protocol_hint = suggested_protocol_hint
            existing.save(update_fields=["detected_protocol", "suggested_protocol_hint"])
            DiscoveredEndpoint.objects.filter(discovery=discovery, host=host, port=port, transport=transport).exclude(id=existing.id).delete()
        else:
            DiscoveredEndpoint.objects.create(
                discovery=discovery,
                host=host,
                port=port,
                transport=transport,
                detected_protocol=detected_protocol,
                suggested_protocol_hint=suggested_protocol_hint,
            )
        saved += 1
    return saved


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
