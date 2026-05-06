import os
import socket
import struct

from .models import DiscoveryEndpoint
from .registry import ProbeRegistry, ProbeSpec


IKE_PORTS = frozenset({500, 4500})
IKE_NEXT_PAYLOAD_SA = 33
IKE_NEXT_PAYLOAD_KE = 34
IKE_NEXT_PAYLOAD_NONCE = 40
IKE_EXCHANGE_SA_INIT = 34
IKE_FLAGS_INITIATOR = 0x08
IKE_VERSION_2 = 0x20


def probe_ike(host: str, port: int, timeout_sec: float) -> DiscoveryEndpoint | None:
    natt = port == 4500
    packet, initiator_spi = _build_ike_sa_init(natt=natt)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(max(timeout_sec, 0.75))
            sock.sendto(packet, (host, port))
            response, _addr = sock.recvfrom(4096)
    except OSError:
        return None
    offset = 4 if response.startswith(b"\x00\x00\x00\x00") else 0
    if len(response) < offset + 28 or response[offset : offset + 8] != initiator_spi:
        return None
    return DiscoveryEndpoint(
        host=host,
        port=port,
        transport="UDP",
        detected_protocol="IKE",
        suggested_protocol_hint="IKE",
    )


def _build_ike_sa_init(natt: bool) -> tuple[bytes, bytes]:
    initiator_spi = os.urandom(8)
    sa_payload = _sa_payload()
    ke_payload = _ke_payload()
    nonce_payload = _nonce_payload()
    body = sa_payload + ke_payload + nonce_payload
    header = struct.pack(
        "!8s8sBBBBII",
        initiator_spi,
        b"\x00" * 8,
        IKE_NEXT_PAYLOAD_SA,
        IKE_VERSION_2,
        IKE_EXCHANGE_SA_INIT,
        IKE_FLAGS_INITIATOR,
        0,
        28 + len(body),
    )
    packet = header + body
    if natt:
        packet = b"\x00\x00\x00\x00" + packet
    return packet, initiator_spi


def _sa_payload() -> bytes:
    transforms = b"".join(
        [
            _transform(more=True, transform_type=1, transform_id=12),
            _transform(more=True, transform_type=2, transform_id=5),
            _transform(more=True, transform_type=3, transform_id=12),
            _transform(more=False, transform_type=4, transform_id=14),
        ]
    )
    proposal = struct.pack("!BBHBBBB", 0, 0, 8 + len(transforms), 1, 1, 0, 4) + transforms
    return struct.pack("!BBH", IKE_NEXT_PAYLOAD_KE, 0, 4 + len(proposal)) + proposal


def _transform(more: bool, transform_type: int, transform_id: int) -> bytes:
    next_transform = 3 if more else 0
    return struct.pack("!BBHBBH", next_transform, 0, 8, transform_type, 0, transform_id)


def _ke_payload() -> bytes:
    key_exchange_data = os.urandom(256)
    body = struct.pack("!HH", 14, 0) + key_exchange_data
    return struct.pack("!BBH", IKE_NEXT_PAYLOAD_NONCE, 0, 4 + len(body)) + body


def _nonce_payload() -> bytes:
    nonce = os.urandom(32)
    return struct.pack("!BBH", 0, 0, 4 + len(nonce)) + nonce


def register(registry: ProbeRegistry) -> None:
    registry.register(ProbeSpec(name="ike", transport="UDP", ports=IKE_PORTS, run=probe_ike))
