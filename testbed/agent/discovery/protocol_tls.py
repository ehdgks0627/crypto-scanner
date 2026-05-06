import ipaddress
import socket
import ssl

from .models import DiscoveryEndpoint
from .registry import ProbeRegistry, ProbeSpec


TLS_PORTS = frozenset({443, 465, 993, 995, 3306, 5000, 6380, 8200, 8443, 8883, 9090, 9093, 9200, 9443, 15017})


def probe_tls(host: str, port: int, timeout_sec: float) -> DiscoveryEndpoint | None:
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
        return None

    detected_protocol, suggested_hint = _protocol_for_tls_port(port)
    return DiscoveryEndpoint(
        host=host,
        port=port,
        transport="TCP",
        detected_protocol=detected_protocol,
        suggested_protocol_hint=suggested_hint,
    )


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


def register(registry: ProbeRegistry) -> None:
    registry.register(ProbeSpec(name="tls", transport="TCP", ports=TLS_PORTS, run=probe_tls))
