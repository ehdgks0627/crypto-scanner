import ipaddress
import math
import os
import socket
import ssl
import time

from .models import DiscoveryEndpoint
from .registry import ProbeRegistry, ProbeSpec


TLS_PORTS = frozenset({443, 465, 993, 995, 3306, 5000, 6380, 8200, 8443, 8883, 9090, 9093, 9200, 9443, 15017})


def probe_tls(host: str, port: int, timeout_sec: float) -> DiscoveryEndpoint | None:
    sample_count = _availability_sample_count()
    if sample_count > 0:
        availability_metrics = measure_tls_availability(host, port, timeout_sec, sample_count)
        if availability_metrics.get("successful_handshakes", 0) == 0:
            return None
    elif not _quick_tls_probe(host, port, timeout_sec):
        return None
    else:
        availability_metrics = {}

    detected_protocol, suggested_hint = _protocol_for_tls_port(port)
    return DiscoveryEndpoint(
        host=host,
        port=port,
        transport="TCP",
        detected_protocol=detected_protocol,
        suggested_protocol_hint=suggested_hint,
        availability_metrics=availability_metrics,
    )


def _quick_tls_probe(host: str, port: int, timeout_sec: float) -> bool:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    server_hostname = host if _is_hostname(host) else None
    try:
        with socket.create_connection((host, port), timeout=timeout_sec) as raw_sock:
            raw_sock.settimeout(timeout_sec)
            with context.wrap_socket(raw_sock, server_hostname=server_hostname):
                pass
    except (OSError, ssl.SSLError):
        return False
    return True


def measure_tls_availability(host: str, port: int, timeout_sec: float, sample_count: int | None = None) -> dict:
    requested_samples = sample_count if sample_count is not None else _availability_sample_count()
    requested_samples = max(1, min(int(requested_samples), 50))
    samples = []
    failures = 0
    timeouts = 0

    for _index in range(requested_samples):
        try:
            samples.append(_measure_tls_sample(host, port, timeout_sec))
        except TimeoutError:
            failures += 1
            timeouts += 1
        except (OSError, ssl.SSLError):
            failures += 1

    metrics = {
        "measurement_type": "tls_availability_check",
        "sample_count": requested_samples,
        "successful_handshakes": len(samples),
        "failure_rate": round(failures / requested_samples, 4),
        "timeout_rate": round(timeouts / requested_samples, 4),
    }
    if not samples:
        return metrics

    metrics.update(
        {
            "tcp_connect_ms": _series(sample["tcp_connect_ms"] for sample in samples),
            "handshake_ms": _series(sample["handshake_ms"] for sample in samples),
            "handshake_bytes_sent": int(_percentile([sample["handshake_bytes_sent"] for sample in samples], 0.95)),
            "handshake_bytes_received": int(_percentile([sample["handshake_bytes_received"] for sample in samples], 0.95)),
            "tls": {
                "versions": _counts(sample.get("tls_version") for sample in samples),
                "cipher_suites": _counts(sample.get("cipher_suite") for sample in samples),
                "alpn_protocols": _counts(sample.get("alpn_protocol") or "none" for sample in samples),
            },
        }
    )

    ttfb_samples = [sample["ttfb_ms"] for sample in samples if sample.get("ttfb_ms") is not None]
    total_samples = [sample["total_request_ms"] for sample in samples if sample.get("total_request_ms") is not None]
    if ttfb_samples:
        metrics["ttfb_ms"] = _series(ttfb_samples)
    if total_samples:
        metrics["total_request_ms"] = _series(total_samples)
    return metrics


def _measure_tls_sample(host: str, port: int, timeout_sec: float) -> dict:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    server_hostname = host if _is_hostname(host) else None
    inbio = ssl.MemoryBIO()
    outbio = ssl.MemoryBIO()
    ssl_object = context.wrap_bio(inbio, outbio, server_side=False, server_hostname=server_hostname)

    connect_start = time.perf_counter()
    with socket.create_connection((host, port), timeout=timeout_sec) as sock:
        sock.settimeout(timeout_sec)
        tcp_connect_ms = _elapsed_ms(connect_start)
        handshake_start = time.perf_counter()
        sent = 0
        received = 0
        while True:
            try:
                ssl_object.do_handshake()
                sent += _flush_outgoing(sock, outbio)
                break
            except ssl.SSLWantReadError:
                sent += _flush_outgoing(sock, outbio)
                received += _read_incoming(sock, inbio)
            except ssl.SSLWantWriteError:
                sent += _flush_outgoing(sock, outbio)

        sample = {
            "tcp_connect_ms": tcp_connect_ms,
            "handshake_ms": _elapsed_ms(handshake_start),
            "handshake_bytes_sent": sent,
            "handshake_bytes_received": received,
            "tls_version": ssl_object.version(),
            "cipher_suite": (ssl_object.cipher() or ("UNKNOWN",))[0],
            "alpn_protocol": ssl_object.selected_alpn_protocol(),
        }
        if _should_measure_http(port):
            sample.update(_measure_http_request(sock, ssl_object, inbio, outbio, host, timeout_sec))
        return sample


def _measure_http_request(sock, ssl_object, inbio, outbio, host: str, timeout_sec: float) -> dict:
    path = os.getenv("DISCOVERY_AVAILABILITY_HTTP_PATH", os.getenv("DISCOVERY_PERF_HTTP_PATH", "/"))
    request = f"HEAD {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode("ascii")
    started_at = time.perf_counter()
    ssl_object.write(request)
    _flush_outgoing(sock, outbio)
    first_byte_at = None
    total_plain = 0
    deadline = started_at + timeout_sec

    while time.perf_counter() < deadline:
        try:
            data = ssl_object.read(8192)
            if data:
                total_plain += len(data)
                first_byte_at = first_byte_at or time.perf_counter()
                if b"\r\n\r\n" in data or total_plain >= 16384:
                    break
            else:
                break
        except ssl.SSLWantReadError:
            try:
                _read_incoming(sock, inbio)
            except TimeoutError:
                break
        except ssl.SSLWantWriteError:
            _flush_outgoing(sock, outbio)
        except ssl.SSLError:
            break

    if first_byte_at is None:
        return {}
    return {
        "ttfb_ms": round((first_byte_at - started_at) * 1000, 2),
        "total_request_ms": _elapsed_ms(started_at),
        "response_bytes": total_plain,
    }


def _flush_outgoing(sock: socket.socket, outbio: ssl.MemoryBIO) -> int:
    total = 0
    while True:
        data = outbio.read()
        if not data:
            return total
        sock.sendall(data)
        total += len(data)


def _read_incoming(sock: socket.socket, inbio: ssl.MemoryBIO) -> int:
    try:
        data = sock.recv(16384)
    except TimeoutError:
        raise
    except socket.timeout as exc:
        raise TimeoutError from exc
    if not data:
        raise ssl.SSLError("TLS peer closed during handshake")
    inbio.write(data)
    return len(data)


def _is_hostname(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return False
    except ValueError:
        return True


def _protocol_for_tls_port(port: int) -> tuple[str, str]:
    if port == 465:
        return "SMTPS", "SMTP"
    if port == 993:
        return "IMAPS", "IMAP"
    if port == 995:
        return "POP3S", "POP3"
    if port == 8883:
        return "MQTT_TLS", "TLS"
    return "TLS", "TLS"


def _availability_sample_count() -> int:
    try:
        return int(os.getenv("DISCOVERY_AVAILABILITY_SAMPLES", os.getenv("DISCOVERY_PERF_SAMPLES", "3")))
    except ValueError:
        return 3


def _should_measure_http(port: int) -> bool:
    raw = os.getenv(
        "DISCOVERY_AVAILABILITY_HTTP_PORTS",
        os.getenv("DISCOVERY_PERF_HTTP_PORTS", "443,5000,8200,8443,9090,9200,9443,15017"),
    )
    try:
        return port in {int(item.strip()) for item in raw.split(",") if item.strip()}
    except ValueError:
        return port in {443, 5000, 8200, 8443, 9090, 9200, 9443, 15017}


def _series(values) -> dict:
    numeric = [float(value) for value in values if value is not None]
    return {
        "p50": round(_percentile(numeric, 0.50), 2),
        "p95": round(_percentile(numeric, 0.95), 2),
        "p99": round(_percentile(numeric, 0.99), 2),
        "samples": len(numeric),
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(math.ceil(percentile * len(ordered)) - 1, len(ordered) - 1)
    return ordered[max(index, 0)]


def _counts(values) -> dict:
    counts = {}
    for value in values:
        if value:
            counts[str(value)] = counts.get(str(value), 0) + 1
    return counts


def _elapsed_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)


def register(registry: ProbeRegistry) -> None:
    registry.register(ProbeSpec(name="tls", transport="TCP", ports=TLS_PORTS, run=probe_tls))
