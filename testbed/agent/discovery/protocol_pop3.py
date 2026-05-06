import socket

from .models import DiscoveryEndpoint
from .registry import ProbeRegistry, ProbeSpec


POP3_STARTTLS_PORTS = frozenset({110})


def probe_pop3_starttls(host: str, port: int, timeout_sec: float) -> DiscoveryEndpoint | None:
    try:
        with socket.create_connection((host, port), timeout=timeout_sec) as sock:
            sock.settimeout(timeout_sec)
            banner = sock.recv(512)
    except OSError:
        return None
    if not banner.startswith(b"+OK"):
        return None
    return DiscoveryEndpoint(
        host=host,
        port=port,
        transport="TCP",
        detected_protocol="POP3",
        suggested_protocol_hint="POP3",
    )


def register(registry: ProbeRegistry) -> None:
    registry.register(ProbeSpec(name="pop3-starttls", transport="TCP", ports=POP3_STARTTLS_PORTS, run=probe_pop3_starttls))
