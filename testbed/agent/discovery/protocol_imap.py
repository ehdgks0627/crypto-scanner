import socket

from .models import DiscoveryEndpoint
from .registry import ProbeRegistry, ProbeSpec


IMAP_STARTTLS_PORTS = frozenset({143})


def probe_imap_starttls(host: str, port: int, timeout_sec: float) -> DiscoveryEndpoint | None:
    try:
        with socket.create_connection((host, port), timeout=timeout_sec) as sock:
            sock.settimeout(timeout_sec)
            banner = sock.recv(512)
    except OSError:
        return None
    if b"IMAP" not in banner.upper():
        return None
    return DiscoveryEndpoint(
        host=host,
        port=port,
        transport="TCP",
        detected_protocol="IMAP",
        suggested_protocol_hint="IMAP",
    )


def register(registry: ProbeRegistry) -> None:
    registry.register(ProbeSpec(name="imap-starttls", transport="TCP", ports=IMAP_STARTTLS_PORTS, run=probe_imap_starttls))
