import socket

from .models import DiscoveryEndpoint
from .registry import ProbeRegistry, ProbeSpec


SMTP_STARTTLS_PORTS = frozenset({25, 587})


def probe_smtp_starttls(host: str, port: int, timeout_sec: float) -> DiscoveryEndpoint | None:
    try:
        with socket.create_connection((host, port), timeout=timeout_sec) as sock:
            sock.settimeout(timeout_sec)
            banner = sock.recv(512)
            if not banner.startswith(b"220"):
                return None
            sock.sendall(b"EHLO pqc-discovery-agent.local\r\n")
            response = sock.recv(2048)
    except OSError:
        return None
    detected = "SMTP_STARTTLS" if b"STARTTLS" in response.upper() else "SMTP"
    return DiscoveryEndpoint(
        host=host,
        port=port,
        transport="TCP",
        detected_protocol=detected,
        suggested_protocol_hint="SMTP",
    )


def register(registry: ProbeRegistry) -> None:
    registry.register(ProbeSpec(name="smtp-starttls", transport="TCP", ports=SMTP_STARTTLS_PORTS, run=probe_smtp_starttls))
