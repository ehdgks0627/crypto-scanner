from __future__ import annotations

import errno
import os
import socket
import ssl
import struct
import time
from dataclasses import dataclass
from itertools import groupby

from apps.assets.models import Asset
from apps.jobs import network_scanner
from apps.performance import services
from apps.performance.models import PerformanceEvaluationRun


PROFILE_ATTEMPTS = {
    "smoke": 1,
    "baseline": 3,
    "canary": 3,
    "stress": 5,
}

HTTP_PORTS = {80, 8080}
TLS_PORTS = set(network_scanner.TLS_DIRECT_PORTS)
SMTP_STARTTLS_PORTS = set(network_scanner.SMTP_STARTTLS_PORTS)
TESTBED_TARGET_IPS = {
    "web.testbed.local": "172.31.240.10",
    "web-ec.testbed.local": "172.31.240.10",
    "pqc-tls.testbed.local": "172.31.240.11",
    "ssh.testbed.local": "172.31.240.12",
    "mqtt.testbed.local": "172.31.240.13",
    "ipsec.testbed.local": "172.31.240.14",
    "mail.testbed.local": "172.31.240.15",
    "db.testbed.local": "172.31.240.16",
    "api-gateway.testbed.local": "172.31.240.21",
    "admin-console.testbed.local": "172.31.240.22",
    "mobile-api.testbed.local": "172.31.240.23",
    "auth-oidc.testbed.local": "172.31.240.24",
    "saml-idp.testbed.local": "172.31.240.25",
    "mysql-legacy.testbed.local": "172.31.240.26",
    "redis-cache.testbed.local": "172.31.240.27",
    "kafka-broker.testbed.local": "172.31.240.28",
    "internal-grpc.testbed.local": "172.31.240.29",
    "service-mesh-mtls.testbed.local": "172.31.240.30",
    "gitlab-runner.testbed.local": "172.31.240.31",
    "container-registry.testbed.local": "172.31.240.32",
    "artifact-repo.testbed.local": "172.31.240.33",
    "vault.testbed.local": "172.31.240.34",
    "backup-service.testbed.local": "172.31.240.35",
    "monitoring.testbed.local": "172.31.240.36",
    "logging.testbed.local": "172.31.240.37",
    "legacy-java-app.testbed.local": "172.31.240.38",
}


class ProbeError(Exception):
    def __init__(self, message: str, *, response_code: str = "probe_failed"):
        self.response_code = response_code
        super().__init__(message)


@dataclass(frozen=True)
class Measurement:
    compatibility_status: str
    metrics: dict
    negotiated_algorithm: str = ""
    error_message: str = ""


def run_performance_run(run_id: int) -> dict:
    run = PerformanceEvaluationRun.objects.select_related("snapshot").get(id=run_id)
    services.update_run_status(run, PerformanceEvaluationRun.RUNNING, {"runner": {"state": "running"}})

    assets = list(
        Asset.objects.select_related("target")
        .filter(snapshot_id=run.snapshot_id, target__isnull=False)
        .order_by("target_id", "bom_ref", "id")
    )
    if not assets:
        services.update_run_status(
            run,
            PerformanceEvaluationRun.COMPLETED,
            {
                "runner": {
                    "state": "completed",
                    "measured_assets": 0,
                    "measured_targets": 0,
                    "skipped_assets": Asset.objects.filter(snapshot_id=run.snapshot_id).count(),
                }
            },
        )
        return {"run_id": run.id, "measured_assets": 0, "measured_targets": 0}

    measured_assets = 0
    measured_targets = 0
    failed_targets = 0
    for _target_id, grouped_assets in groupby(assets, key=lambda asset: asset.target_id):
        target_assets = list(grouped_assets)
        target = target_assets[0].target
        measurement = measure_target(target, run.profile)
        measured_targets += 1
        if measurement.compatibility_status in {"FAIL", "ERROR"}:
            failed_targets += 1
        for asset in target_assets:
            services.upsert_result(
                run,
                {
                    "asset_id": asset.id,
                    "compatibility_status": measurement.compatibility_status,
                    "negotiated_algorithm": measurement.negotiated_algorithm,
                    "metrics": measurement.metrics,
                    "error_message": measurement.error_message,
                },
            )
            measured_assets += 1

    services.update_run_status(
        run,
        PerformanceEvaluationRun.COMPLETED,
        {
            "runner": {
                "state": "completed",
                "measured_assets": measured_assets,
                "measured_targets": measured_targets,
                "failed_targets": failed_targets,
            }
        },
    )
    return {
        "run_id": run.id,
        "measured_assets": measured_assets,
        "measured_targets": measured_targets,
        "failed_targets": failed_targets,
    }


def measure_target(target, profile: str) -> Measurement:
    protocol = _target_protocol(target)
    attempts = _attempts_for_profile(profile)
    timeout_sec = _timeout_sec()
    successes: list[dict] = []
    failures: list[BaseException] = []

    for _index in range(attempts):
        try:
            successes.append(_probe_once(target, protocol, timeout_sec))
        except BaseException as exc:
            failures.append(exc)

    return _aggregate_measurements(protocol, attempts, successes, failures)


def _probe_once(target, protocol: str, timeout_sec: float) -> dict:
    if target.transport == "UDP" and protocol == "IKE":
        return _probe_ike(target, timeout_sec)
    if protocol == "SSH" or target.port in {22, 2222}:
        return _probe_ssh(target, timeout_sec)
    if protocol == "SMTP" and target.port in SMTP_STARTTLS_PORTS:
        return _probe_smtp_starttls(target, timeout_sec)
    if target.port == 5432:
        return _probe_postgresql_tls(target, timeout_sec)
    if protocol == "HTTP" or target.port in HTTP_PORTS:
        return _probe_http(target, timeout_sec)
    if protocol in {"TLS", "SMTP", "IMAP", "POP3"} or target.port in TLS_PORTS:
        return _probe_tls(target, timeout_sec)
    return _probe_tcp(target, protocol, timeout_sec)


def _probe_tls(target, timeout_sec: float) -> dict:
    raw_sock = None
    start = time.perf_counter()
    try:
        raw_sock = socket.create_connection((_target_address(target), target.port), timeout=timeout_sec)
        raw_sock.settimeout(timeout_sec)
        connected_at = time.perf_counter()
        context = _tls_context()
        with context.wrap_socket(raw_sock, server_hostname=_sni(target)) as tls_sock:
            completed_at = time.perf_counter()
            cipher = tls_sock.cipher()
            return {
                "protocol": "TLS",
                "tcp_connect_ms": _series([_elapsed_ms(start, connected_at)]),
                "handshake_ms": _series([_elapsed_ms(connected_at, completed_at)]),
                "total_request_ms": _series([_elapsed_ms(start, completed_at)]),
                "response_code": "tls_ok",
                "tls_version": tls_sock.version(),
                "cipher_suite": cipher[0] if cipher else "",
                "negotiated_algorithm": _negotiated_tls_algorithm(tls_sock),
            }
    except BaseException:
        if raw_sock:
            raw_sock.close()
        raise


def _probe_postgresql_tls(target, timeout_sec: float) -> dict:
    raw_sock = None
    start = time.perf_counter()
    try:
        raw_sock = socket.create_connection((_target_address(target), target.port), timeout=timeout_sec)
        raw_sock.settimeout(timeout_sec)
        connected_at = time.perf_counter()
        raw_sock.sendall(struct.pack("!II", 8, network_scanner.POSTGRESQL_SSL_REQUEST_CODE))
        response = raw_sock.recv(1)
        if response != b"S":
            raise ProbeError("PostgreSQL server rejected TLS request", response_code="postgres_tls_rejected")
        context = _tls_context()
        with context.wrap_socket(raw_sock, server_hostname=None) as tls_sock:
            completed_at = time.perf_counter()
            cipher = tls_sock.cipher()
            return {
                "protocol": "TLS",
                "tcp_connect_ms": _series([_elapsed_ms(start, connected_at)]),
                "handshake_ms": _series([_elapsed_ms(connected_at, completed_at)]),
                "total_request_ms": _series([_elapsed_ms(start, completed_at)]),
                "response_code": "postgres_tls_ok",
                "tls_version": tls_sock.version(),
                "cipher_suite": cipher[0] if cipher else "",
                "negotiated_algorithm": _negotiated_tls_algorithm(tls_sock),
            }
    except BaseException:
        if raw_sock:
            raw_sock.close()
        raise


def _probe_smtp_starttls(target, timeout_sec: float) -> dict:
    raw_sock = None
    start = time.perf_counter()
    try:
        raw_sock = socket.create_connection((_target_address(target), target.port), timeout=timeout_sec)
        raw_sock.settimeout(timeout_sec)
        connected_at = time.perf_counter()
        _recv_available(raw_sock, 512)
        raw_sock.sendall(b"EHLO pqc-availability.local\r\n")
        ehlo = _recv_available(raw_sock, 2048)
        if b"STARTTLS" not in ehlo.upper():
            raise ProbeError("SMTP STARTTLS not advertised", response_code="starttls_not_advertised")
        raw_sock.sendall(b"STARTTLS\r\n")
        ready = _recv_available(raw_sock, 512)
        if not ready.startswith(b"220"):
            raise ProbeError("SMTP STARTTLS rejected", response_code="starttls_rejected")
        context = _tls_context()
        with context.wrap_socket(raw_sock, server_hostname=_sni(target)) as tls_sock:
            completed_at = time.perf_counter()
            cipher = tls_sock.cipher()
            return {
                "protocol": "SMTP",
                "tcp_connect_ms": _series([_elapsed_ms(start, connected_at)]),
                "handshake_ms": _series([_elapsed_ms(connected_at, completed_at)]),
                "total_request_ms": _series([_elapsed_ms(start, completed_at)]),
                "response_code": "starttls_ok",
                "tls_version": tls_sock.version(),
                "cipher_suite": cipher[0] if cipher else "",
                "negotiated_algorithm": _negotiated_tls_algorithm(tls_sock),
            }
    except BaseException:
        if raw_sock:
            raw_sock.close()
        raise


def _probe_ssh(target, timeout_sec: float) -> dict:
    start = time.perf_counter()
    with socket.create_connection((_target_address(target), target.port), timeout=timeout_sec) as sock:
        connected_at = time.perf_counter()
        sock.settimeout(timeout_sec)
        banner = sock.recv(255).decode("ascii", errors="replace").strip()
        completed_at = time.perf_counter()
        if not banner.startswith("SSH-"):
            raise ProbeError("SSH banner not received", response_code="ssh_banner_missing")
        return {
            "protocol": "SSH",
            "tcp_connect_ms": _series([_elapsed_ms(start, connected_at)]),
            "handshake_ms": _series([_elapsed_ms(connected_at, completed_at)]),
            "total_request_ms": _series([_elapsed_ms(start, completed_at)]),
            "response_code": "ssh_banner",
            "negotiated_algorithm": banner.split(" ", 1)[0][:128],
        }


def _probe_ike(target, timeout_sec: float) -> dict:
    natt = target.port == 4500
    packet, initiator_spi = network_scanner._build_ike_sa_init(natt=natt)
    start = time.perf_counter()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout_sec)
        sock.sendto(packet, (_target_address(target), target.port))
        response, _addr = sock.recvfrom(4096)
    completed_at = time.perf_counter()
    offset = 4 if response.startswith(b"\x00\x00\x00\x00") else 0
    if len(response) < offset + 28 or response[offset : offset + 8] != initiator_spi:
        raise ProbeError("IKE response mismatch", response_code="ike_response_mismatch")
    return {
        "protocol": "IKE",
        "handshake_ms": _series([_elapsed_ms(start, completed_at)]),
        "total_request_ms": _series([_elapsed_ms(start, completed_at)]),
        "response_code": "ike_sa_init_response",
        "negotiated_algorithm": "IKEv2 SA_INIT",
    }


def _probe_http(target, timeout_sec: float) -> dict:
    start = time.perf_counter()
    with socket.create_connection((_target_address(target), target.port), timeout=timeout_sec) as sock:
        connected_at = time.perf_counter()
        sock.settimeout(timeout_sec)
        request = f"GET / HTTP/1.0\r\nHost: {target.host}\r\nConnection: close\r\n\r\n".encode("ascii", errors="ignore")
        sock.sendall(request)
        first_chunk = sock.recv(1024)
        completed_at = time.perf_counter()
    first_line = first_chunk.splitlines()[0].decode("ascii", errors="replace") if first_chunk else ""
    if not first_line.startswith("HTTP/"):
        raise ProbeError("HTTP response line not received", response_code="http_response_missing")
    return {
        "protocol": "HTTP",
        "tcp_connect_ms": _series([_elapsed_ms(start, connected_at)]),
        "ttfb_ms": _series([_elapsed_ms(connected_at, completed_at)]),
        "total_request_ms": _series([_elapsed_ms(start, completed_at)]),
        "response_code": first_line[:64],
        "negotiated_algorithm": "HTTP",
    }


def _probe_tcp(target, protocol: str, timeout_sec: float) -> dict:
    start = time.perf_counter()
    with socket.create_connection((_target_address(target), target.port), timeout=timeout_sec):
        completed_at = time.perf_counter()
    return {
        "protocol": protocol,
        "tcp_connect_ms": _series([_elapsed_ms(start, completed_at)]),
        "handshake_ms": _series([_elapsed_ms(start, completed_at)]),
        "total_request_ms": _series([_elapsed_ms(start, completed_at)]),
        "response_code": "tcp_connect_ok",
        "negotiated_algorithm": "TCP",
    }


def _aggregate_measurements(protocol: str, attempts: int, successes: list[dict], failures: list[BaseException]) -> Measurement:
    success_count = len(successes)
    failure_count = len(failures)
    timeout_count = sum(1 for failure in failures if _is_timeout(failure))
    metrics = _merge_success_metrics(protocol, successes)
    metrics["sample_count"] = attempts
    metrics["failure_rate"] = round(failure_count / attempts, 4)
    metrics["timeout_rate"] = round(timeout_count / attempts, 4)

    if protocol == "IKE":
        metrics["successful_negotiations"] = success_count
        metrics["failed_negotiations"] = failure_count
        metrics["total_negotiations"] = attempts
    else:
        metrics["successful_handshakes"] = success_count
        metrics["failed_handshakes"] = failure_count
        metrics["total_handshakes"] = attempts

    negotiated_algorithm = _first_text(successes, "negotiated_algorithm")
    if successes:
        if failures:
            metrics["failure_reason"] = _error_message(failures[-1])
            metrics["response_code"] = metrics.get("response_code") or _error_code(failures[-1])
        return Measurement(
            compatibility_status="PASS",
            metrics=metrics,
            negotiated_algorithm=negotiated_algorithm,
            error_message="",
        )

    failure = failures[-1] if failures else ProbeError("No probe result")
    metrics["response_code"] = _error_code(failure)
    metrics["failure_reason"] = _error_message(failure)
    return Measurement(
        compatibility_status="ERROR" if isinstance(failure, socket.gaierror) else "FAIL",
        metrics=metrics,
        negotiated_algorithm=negotiated_algorithm,
        error_message=_error_message(failure)[:255],
    )


def _merge_success_metrics(protocol: str, successes: list[dict]) -> dict:
    metrics = {"protocol": protocol}
    if not successes:
        return metrics
    for key in ("tcp_connect_ms", "handshake_ms", "ttfb_ms", "total_request_ms"):
        values = [_series_value(success.get(key), "p95") for success in successes]
        values = [value for value in values if value is not None]
        if values:
            metrics[key] = _series(values)
    for key in ("response_code", "tls_version", "cipher_suite"):
        value = _first_text(successes, key)
        if value:
            metrics[key] = value
    return metrics


def _series(values: list[float]) -> dict:
    ordered = sorted(round(float(value), 2) for value in values)
    if not ordered:
        return {"p50": 0.0, "p95": 0.0, "samples": 0}
    return {
        "p50": _percentile(ordered, 0.50),
        "p95": _percentile(ordered, 0.95),
        "samples": len(ordered),
    }


def _percentile(ordered: list[float], percentile: float) -> float:
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percentile)))
    return ordered[index]


def _series_value(value, percentile: str) -> float | None:
    if isinstance(value, dict) and isinstance(value.get(percentile), (int, float)):
        return float(value[percentile])
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _elapsed_ms(start: float, end: float) -> float:
    return (end - start) * 1000


def _target_protocol(target) -> str:
    protocol = str(target.protocol_hint or "UNKNOWN").upper()
    if target.transport == "UDP" and target.port in {500, 4500}:
        return "IKE"
    if target.port in {22, 2222}:
        return "SSH"
    if target.port in HTTP_PORTS:
        return "HTTP"
    return protocol


def _target_address(target) -> str:
    return target.ip or TESTBED_TARGET_IPS.get(target.host, target.host)


def _sni(target) -> str | None:
    value = target.sni or target.host
    if not value:
        return None
    try:
        socket.inet_pton(socket.AF_INET, value)
        return None
    except OSError:
        pass
    try:
        socket.inet_pton(socket.AF_INET6, value)
        return None
    except OSError:
        return value


def _tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    try:
        context.set_alpn_protocols(network_scanner.TLS_ALPN_PROTOCOLS)
    except NotImplementedError:
        pass
    return context


def _recv_available(sock: socket.socket, size: int) -> bytes:
    chunks = []
    original_timeout = sock.gettimeout()
    deadline = time.perf_counter() + max(float(original_timeout or 0.5), 0.5)
    sock.settimeout(0.15)
    try:
        while time.perf_counter() < deadline:
            try:
                chunk = sock.recv(size)
            except socket.timeout:
                if chunks:
                    break
                continue
            if not chunk:
                break
            chunks.append(chunk)
            if sum(len(item) for item in chunks) >= size:
                break
    finally:
        sock.settimeout(original_timeout)
    return b"".join(chunks)


def _negotiated_tls_algorithm(tls_sock) -> str:
    cipher = tls_sock.cipher()
    cipher_name = cipher[0] if cipher else ""
    version = tls_sock.version() or ""
    return " ".join(part for part in [version, cipher_name] if part)[:128]


def _attempts_for_profile(profile: str) -> int:
    configured = os.getenv("PERFORMANCE_RUN_SAMPLES")
    if configured:
        try:
            return max(1, min(20, int(configured)))
        except ValueError:
            pass
    return PROFILE_ATTEMPTS.get(profile, 1)


def _timeout_sec() -> float:
    try:
        return max(0.2, min(30.0, float(os.getenv("PERFORMANCE_RUN_TIMEOUT_SEC", "2.0"))))
    except ValueError:
        return 2.0


def _first_text(items: list[dict], key: str) -> str:
    for item in items:
        value = item.get(key)
        if value:
            return str(value)
    return ""


def _is_timeout(exc: BaseException) -> bool:
    return isinstance(exc, (socket.timeout, TimeoutError)) or "timed out" in str(exc).lower()


def _error_code(exc: BaseException) -> str:
    if isinstance(exc, ProbeError):
        return exc.response_code
    if isinstance(exc, socket.gaierror):
        return "dns_resolution_failed"
    if _is_timeout(exc):
        return "connection_timeout"
    if isinstance(exc, ConnectionRefusedError) or getattr(exc, "errno", None) == errno.ECONNREFUSED:
        return "connection_refused"
    if isinstance(exc, ssl.SSLError):
        return "tls_handshake_failed"
    return "connection_failed"


def _error_message(exc: BaseException) -> str:
    message = str(exc).strip()
    return message or exc.__class__.__name__
