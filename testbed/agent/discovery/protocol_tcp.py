import socket

from .models import DiscoveryEndpoint
from .registry import ProbeRegistry, ProbeSpec


def probe_tcp(host: str, port: int, timeout_sec: float) -> DiscoveryEndpoint | None:
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            pass
    except OSError:
        return None
    return DiscoveryEndpoint(
        host=host,
        port=port,
        transport="TCP",
        detected_protocol="TCP",
        suggested_protocol_hint=suggested_hint_for_port(port),
    )


def suggested_hint_for_port(port: int) -> str:
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


def register(registry: ProbeRegistry) -> None:
    registry.register(ProbeSpec(name="tcp-fallback", transport="TCP", ports=None, run=probe_tcp, fallback=True))
