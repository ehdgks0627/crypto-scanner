import socket
import ssl
import struct

from .models import DiscoveryEndpoint
from .registry import ProbeRegistry, ProbeSpec


POSTGRESQL_PORTS = frozenset({5432})
SSL_REQUEST_CODE = 80877103


def probe_postgresql_tls(host: str, port: int, timeout_sec: float) -> DiscoveryEndpoint | None:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host, port), timeout=timeout_sec) as raw_sock:
            raw_sock.settimeout(timeout_sec)
            raw_sock.sendall(struct.pack("!II", 8, SSL_REQUEST_CODE))
            response = raw_sock.recv(1)
            if response == b"S":
                with context.wrap_socket(raw_sock, server_hostname=None):
                    pass
                detected = "POSTGRES_TLS"
            elif response == b"N":
                detected = "POSTGRES"
            else:
                return None
    except (OSError, ssl.SSLError):
        return None
    return DiscoveryEndpoint(
        host=host,
        port=port,
        transport="TCP",
        detected_protocol=detected,
        suggested_protocol_hint="TLS",
    )


def register(registry: ProbeRegistry) -> None:
    registry.register(ProbeSpec(name="postgresql-tls", transport="TCP", ports=POSTGRESQL_PORTS, run=probe_postgresql_tls))
