import socket

from .models import DiscoveryEndpoint
from .registry import ProbeRegistry, ProbeSpec


SSH_PORTS = frozenset({22, 2222})


def probe_ssh(host: str, port: int, timeout_sec: float) -> DiscoveryEndpoint | None:
    try:
        with socket.create_connection((host, port), timeout=timeout_sec) as sock:
            sock.settimeout(timeout_sec)
            banner = sock.recv(64)
    except OSError:
        return None
    if not banner.startswith(b"SSH-"):
        return None
    return DiscoveryEndpoint(
        host=host,
        port=port,
        transport="TCP",
        detected_protocol="SSH",
        suggested_protocol_hint="SSH",
    )


def register(registry: ProbeRegistry) -> None:
    registry.register(ProbeSpec(name="ssh", transport="TCP", ports=SSH_PORTS, run=probe_ssh))
