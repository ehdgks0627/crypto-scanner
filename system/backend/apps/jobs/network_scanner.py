import base64
import ipaddress
import json
import os
import re
import socket
import ssl
import struct
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from hashlib import sha256

from apps.jobs.scan_assets import AssetCandidate, family_from_algorithm, stable_bom_ref


TLS_DIRECT_PORTS = {443, 465, 993, 995, 3306, 5000, 6380, 8200, 8443, 8883, 9090, 9093, 9200, 9443, 15017}
MQTT_TLS_PORTS = {8883}
SMTP_STARTTLS_PORTS = {25, 587}
POSTGRESQL_SSL_REQUEST_CODE = 80877103
TLS_ALPN_PROTOCOLS = ["h2", "http/1.1", "mqtt", "imap", "pop3", "smtp"]
TLS13_CIPHER_PROBE_CANDIDATES = (
    "TLS_AES_256_GCM_SHA384",
    "TLS_CHACHA20_POLY1305_SHA256",
    "TLS_AES_128_GCM_SHA256",
)
TLS12_CIPHER_PROBE_CANDIDATES = (
    "ECDHE-RSA-AES256-GCM-SHA384",
    "ECDHE-ECDSA-AES128-GCM-SHA256",
    "DHE-RSA-AES256-GCM-SHA384",
    "ECDHE-RSA-AES128-GCM-SHA256",
    "ECDHE-ECDSA-AES256-GCM-SHA384",
    "AES128-SHA",
    "AES256-SHA",
)
SSH_KEY_TYPES = "rsa,ecdsa,ed25519"

IKE_NEXT_PAYLOAD_SA = 33
IKE_NEXT_PAYLOAD_KE = 34
IKE_NEXT_PAYLOAD_NONCE = 40
IKE_EXCHANGE_SA_INIT = 34
IKE_FLAGS_INITIATOR = 0x08
IKE_VERSION_2 = 0x20

IKE_TRANSFORM_TYPE = {
    1: "encryption",
    2: "prf",
    3: "integrity",
    4: "dh_group",
}
IKE_ENCRYPTION = {
    12: "AES-CBC",
    13: "AES-CTR",
    18: "AES-GCM-8",
    19: "AES-GCM-12",
    20: "AES-GCM-16",
    28: "ChaCha20-Poly1305",
}
IKE_PRF = {
    2: "HMAC-SHA1",
    5: "HMAC-SHA2-256",
    6: "HMAC-SHA2-384",
    7: "HMAC-SHA2-512",
}
IKE_INTEGRITY = {
    2: "HMAC-SHA1-96",
    12: "HMAC-SHA2-256-128",
    13: "HMAC-SHA2-384-192",
    14: "HMAC-SHA2-512-256",
}
IKE_DH_GROUPS = {
    14: "MODP-2048",
    15: "MODP-3072",
    16: "MODP-4096",
    19: "ECP-256",
    20: "ECP-384",
    21: "ECP-521",
    31: "Curve25519",
    32: "Curve448",
}


@dataclass(frozen=True)
class TlsProbeResult:
    sni: str | None
    der_chain: list[bytes]
    tls_version: str | None
    cipher_suite: str | None
    alpn: str | None
    supported_cipher_suites: tuple[str, ...] = ()
    pqc_readiness: dict | None = None


def scan_network_target(target, timeout_sec: float = 5.0) -> list[AssetCandidate]:
    protocol_hint = str(target.protocol_hint or "UNKNOWN").upper()
    if target.transport == "UDP" and protocol_hint == "IKE":
        return _scan_ike(target, timeout_sec)
    if protocol_hint == "SSH" or target.port in {22, 2222}:
        return _scan_ssh(target, timeout_sec)
    if protocol_hint == "SMTP" and target.port in SMTP_STARTTLS_PORTS:
        return _scan_smtp_starttls(target, timeout_sec)
    if target.port == 5432:
        return _scan_postgresql_tls(target, timeout_sec)
    if protocol_hint in {"TLS", "SMTP", "IMAP", "POP3"} or target.port in TLS_DIRECT_PORTS:
        return _scan_tls(target, timeout_sec)
    if protocol_hint == "UNKNOWN":
        return _scan_unknown(target, timeout_sec)
    return [_tcp_fallback_candidate(target)]


def _scan_unknown(target, timeout_sec: float) -> list[AssetCandidate]:
    for scanner in (_scan_tls, _scan_ssh):
        try:
            candidates = scanner(target, timeout_sec)
        except Exception:
            continue
        if candidates:
            return candidates
    return [_tcp_fallback_candidate(target)]


def _scan_tls(target, timeout_sec: float) -> list[AssetCandidate]:
    candidates = []
    seen_sni = set()
    pending_sni = _initial_sni_names(target)

    while pending_sni:
        sni = pending_sni.pop(0)
        sni_key = sni or ""
        if sni_key in seen_sni:
            continue
        seen_sni.add(sni_key)
        result = _tls_probe(target, timeout_sec, sni=sni)
        candidates.extend(_tls_candidates_from_result(target, result, source="tls"))
        for san in _subject_alt_names_from_chain(result.der_chain):
            if san not in seen_sni and san not in pending_sni:
                pending_sni.append(san)
        for alias in _known_sni_aliases(target):
            if alias not in seen_sni and alias not in pending_sni:
                pending_sni.append(alias)

    return candidates


def _scan_smtp_starttls(target, timeout_sec: float) -> list[AssetCandidate]:
    address = _target_address(target)
    with socket.create_connection((address, target.port), timeout=timeout_sec) as raw_sock:
        raw_sock.settimeout(timeout_sec)
        raw_sock.recv(512)
        raw_sock.sendall(b"EHLO pqc-scan-worker.local\r\n")
        response = raw_sock.recv(2048)
        if b"STARTTLS" not in response.upper():
            return [_protocol_policy_candidate(target, "SMTP", "SMTP without STARTTLS advertisement")]
        raw_sock.sendall(b"STARTTLS\r\n")
        ready = raw_sock.recv(512)
        if not ready.startswith(b"220"):
            return [_protocol_policy_candidate(target, "SMTP", "SMTP STARTTLS rejected")]
        context = _tls_context()
        sni = target.sni or target.host
        with context.wrap_socket(raw_sock, server_hostname=sni) as tls_sock:
            der = tls_sock.getpeercert(binary_form=True)
            version = tls_sock.version()
            cipher = _cipher_name(tls_sock)
    chain = _openssl_certificate_chain(target, timeout_sec, sni=sni, starttls="smtp") or ([der] if der else [])
    result = TlsProbeResult(sni=sni, der_chain=chain, tls_version=version, cipher_suite=cipher, alpn=None)
    return _tls_candidates_from_result(target, result, source="smtp-starttls")


def _scan_postgresql_tls(target, timeout_sec: float) -> list[AssetCandidate]:
    address = _target_address(target)
    with socket.create_connection((address, target.port), timeout=timeout_sec) as raw_sock:
        raw_sock.settimeout(timeout_sec)
        raw_sock.sendall(struct.pack("!II", 8, POSTGRESQL_SSL_REQUEST_CODE))
        response = raw_sock.recv(1)
        if response != b"S":
            return [_protocol_policy_candidate(target, "PostgreSQL", "PostgreSQL TLS disabled")]
        context = _tls_context()
        with context.wrap_socket(raw_sock, server_hostname=None) as tls_sock:
            der = tls_sock.getpeercert(binary_form=True)
            version = tls_sock.version()
            cipher = _cipher_name(tls_sock)
    chain = _openssl_certificate_chain(target, timeout_sec, sni=None, starttls="postgres") or ([der] if der else [])
    result = TlsProbeResult(sni=None, der_chain=chain, tls_version=version, cipher_suite=cipher, alpn=None)
    return _tls_candidates_from_result(target, result, source="postgresql-tls")


def _tls_probe(target, timeout_sec: float, sni: str | None = None, starttls: str | None = None) -> TlsProbeResult:
    if starttls is not None:
        raise ValueError("starttls probes are handled by protocol-specific scanners")
    address = _target_address(target)
    context = _tls_context()
    with socket.create_connection((address, target.port), timeout=timeout_sec) as raw_sock:
        raw_sock.settimeout(timeout_sec)
        with context.wrap_socket(raw_sock, server_hostname=sni) as tls_sock:
            der = tls_sock.getpeercert(binary_form=True)
            version = tls_sock.version()
            cipher = _cipher_name(tls_sock)
            alpn = tls_sock.selected_alpn_protocol()
    chain = _openssl_certificate_chain(target, timeout_sec, sni=sni) or ([der] if der else [])
    supported_cipher_suites = _accepted_tls_cipher_suites(target, timeout_sec, sni=sni)
    pqc_readiness = _pqc_readiness_metadata(target, timeout_sec, sni=sni)
    return TlsProbeResult(
        sni=sni,
        der_chain=chain,
        tls_version=version,
        cipher_suite=cipher,
        alpn=alpn,
        supported_cipher_suites=tuple(supported_cipher_suites),
        pqc_readiness=pqc_readiness,
    )


def _tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    try:
        context.set_alpn_protocols(TLS_ALPN_PROTOCOLS)
    except NotImplementedError:
        pass
    return context


def _cipher_name(tls_sock) -> str | None:
    cipher = tls_sock.cipher()
    return cipher[0] if cipher else None


def _dedupe(values: list[str | None]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _accepted_tls_cipher_suites(target, timeout_sec: float, sni: str | None = None) -> list[str]:
    if str(os.getenv("NETWORK_TLS_CIPHER_ENUMERATION", "1")).lower() in {"0", "false", "no"}:
        return []
    accepted = []
    for cipher_name in _cipher_probe_candidates():
        if cipher_name.startswith("TLS_"):
            negotiated = _probe_tls13_cipher_suite(target, timeout_sec, sni=sni, cipher_name=cipher_name)
        else:
            negotiated = _probe_tls12_cipher_suite(target, timeout_sec, sni=sni, cipher_name=cipher_name)
        if negotiated and negotiated not in accepted:
            accepted.append(negotiated)
    return accepted


def _cipher_probe_candidates() -> list[str]:
    limit = _cipher_enumeration_limit()
    candidates = [*TLS13_CIPHER_PROBE_CANDIDATES, *TLS12_CIPHER_PROBE_CANDIDATES]
    try:
        for cipher in _tls_context().get_ciphers():
            name = cipher.get("name")
            protocol = cipher.get("protocol")
            if name and protocol != "TLSv1.3":
                candidates.append(str(name))
    except ssl.SSLError:
        pass
    return _dedupe(candidates)[:limit]


def _cipher_enumeration_limit() -> int:
    try:
        return max(0, int(os.getenv("NETWORK_TLS_CIPHER_ENUMERATION_LIMIT", "24")))
    except ValueError:
        return 24


def _probe_tls12_cipher_suite(target, timeout_sec: float, sni: str | None, cipher_name: str) -> str | None:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.TLSv1_2
    try:
        context.set_ciphers(cipher_name)
    except ssl.SSLError:
        return None
    try:
        with socket.create_connection((_target_address(target), target.port), timeout=timeout_sec) as raw_sock:
            raw_sock.settimeout(timeout_sec)
            with context.wrap_socket(raw_sock, server_hostname=sni) as tls_sock:
                return _cipher_name(tls_sock)
    except (OSError, ssl.SSLError):
        return None


def _probe_tls13_cipher_suite(target, timeout_sec: float, sni: str | None, cipher_name: str) -> str | None:
    cmd = [
        "openssl",
        "s_client",
        "-connect",
        f"{_target_address(target)}:{target.port}",
        "-tls1_3",
        "-ciphersuites",
        cipher_name,
        "-brief",
    ]
    if sni:
        cmd.extend(["-servername", sni])
    try:
        result = subprocess.run(
            cmd,
            input="",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=max(timeout_sec, 1.0) + 2.0,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    match = re.search(r"Ciphersuite:\s*(?P<cipher>[A-Za-z0-9_-]+)", result.stdout or "")
    if not match:
        return None
    negotiated = match.group("cipher")
    return negotiated if negotiated == cipher_name else None


def _pqc_readiness_metadata(target, timeout_sec: float, sni: str | None) -> dict | None:
    if str(os.getenv("NETWORK_TLS_PQC_READINESS", "1")).lower() in {"0", "false", "no"}:
        return None
    if target.port not in _pqc_readiness_ports():
        return None
    path = os.getenv("NETWORK_TLS_PQC_READINESS_PATH", "/.well-known/pqc-readiness.json")
    host_header = sni or target.sni or target.host
    context = _tls_context()
    try:
        with socket.create_connection((_target_address(target), target.port), timeout=timeout_sec) as raw_sock:
            raw_sock.settimeout(max(0.5, min(timeout_sec, 2.0)))
            with context.wrap_socket(raw_sock, server_hostname=sni) as tls_sock:
                request = f"GET {path} HTTP/1.1\r\nHost: {host_header}\r\nConnection: close\r\n\r\n"
                tls_sock.sendall(request.encode("ascii"))
                response = _recv_http_response(tls_sock)
    except (OSError, ssl.SSLError, TimeoutError):
        return None
    try:
        header, body = response.split(b"\r\n\r\n", 1)
    except ValueError:
        return None
    if not header.startswith(b"HTTP/1.") or b" 200 " not in header[:32]:
        return None
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _recv_http_response(tls_sock) -> bytes:
    chunks = []
    total = 0
    while total < 16384:
        try:
            chunk = tls_sock.recv(4096)
        except socket.timeout as exc:
            raise TimeoutError from exc
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if b"\r\n\r\n" in b"".join(chunks) and b"}" in chunk:
            break
    return b"".join(chunks)


def _pqc_readiness_ports() -> set[int]:
    raw = os.getenv("NETWORK_TLS_PQC_READINESS_PORTS", "443,5000,8200,8443,9090,9200,9443,15017")
    try:
        return {int(item.strip()) for item in raw.split(",") if item.strip()}
    except ValueError:
        return {443, 5000, 8200, 8443, 9090, 9200, 9443, 15017}


def _tls_candidates_from_result(target, result: TlsProbeResult, source: str) -> list[AssetCandidate]:
    candidates = []
    for index, der in enumerate(result.der_chain):
        candidates.append(_certificate_candidate(target, der, source=source, sni=result.sni, chain_index=index))
    if result.tls_version:
        candidates.append(_tls_version_candidate(target, result))
    for cipher_suite in _dedupe([result.cipher_suite, *result.supported_cipher_suites]):
        candidates.append(_tls_cipher_candidate(target, result, cipher_suite))
    candidates.extend(_pqc_readiness_candidates(target, result))
    if result.alpn:
        candidates.append(_application_protocol_candidate(target, result.alpn.upper(), f"ALPN {result.alpn}", result.sni))
    if target.port in MQTT_TLS_PORTS or result.alpn == "mqtt":
        candidates.append(_application_protocol_candidate(target, "MQTT", "MQTT over TLS", result.sni))
    return candidates


def _pqc_readiness_candidates(target, result: TlsProbeResult) -> list[AssetCandidate]:
    metadata = result.pqc_readiness or {}
    if not metadata or metadata.get("pqc_enabled") is not True:
        return []
    sni_label = result.sni or target.sni or target.host
    signature_algorithm = str(metadata.get("signature_algorithm") or "").strip()
    kem_group = str(metadata.get("kem_group") or metadata.get("key_exchange_group") or "").strip()
    hybrid_group = str(metadata.get("hybrid_group") or "").strip()
    source_metadata = {
        "scanner": "network",
        "type": "pqc_readiness",
        "source": "tls-pqc-readiness",
        "sni": sni_label,
        "evidence_path": metadata.get("evidence_path") or "/.well-known/pqc-readiness.json",
        "hybrid_group": hybrid_group,
        "standard": metadata.get("standard"),
        "implementation": metadata.get("implementation"),
    }
    candidates = []
    if signature_algorithm:
        candidates.append(
            AssetCandidate(
                target_id=target.id,
                scanner_kind="network",
                name=f"{target.host}:{target.port} {sni_label} PQC signature",
                asset_type="certificate",
                algorithm=signature_algorithm,
                algorithm_family=family_from_algorithm(signature_algorithm),
                bom_ref=f"network:pqc-readiness:signature:{stable_bom_ref(target.host, target.port, sni_label, signature_algorithm)}",
                metadata={**source_metadata, "pqc_role": "signature"},
            )
        )
    if kem_group:
        candidates.append(
            AssetCandidate(
                target_id=target.id,
                scanner_kind="network",
                name=f"{target.host}:{target.port} {sni_label} PQC key agreement",
                asset_type="key_agreement",
                algorithm=kem_group,
                algorithm_family=family_from_algorithm(kem_group),
                bom_ref=f"network:pqc-readiness:kem:{stable_bom_ref(target.host, target.port, sni_label, kem_group)}",
                metadata={**source_metadata, "pqc_role": "kem"},
            )
        )
    if hybrid_group:
        candidates.append(
            AssetCandidate(
                target_id=target.id,
                scanner_kind="network",
                name=f"{target.host}:{target.port} {sni_label} hybrid TLS group",
                asset_type="protocol",
                algorithm=hybrid_group,
                algorithm_family=family_from_algorithm(hybrid_group),
                bom_ref=f"network:pqc-readiness:hybrid-group:{stable_bom_ref(target.host, target.port, sni_label, hybrid_group)}",
                metadata={**source_metadata, "pqc_role": "hybrid_group"},
            )
        )
    return candidates


def _initial_sni_names(target) -> list[str | None]:
    names = []
    primary = target.sni or (target.host if _is_hostname(target.host) else None)
    names.append(primary)
    for alias in _known_sni_aliases(target):
        if alias not in names:
            names.append(alias)
    return names


def _known_sni_aliases(target) -> list[str]:
    try:
        from apps.targets.models import Target
    except Exception:
        return []

    address = _resolve_address(_target_address(target))
    if not address:
        return []

    aliases = []
    try:
        queryset = Target.objects.filter(port=target.port, transport=target.transport).exclude(id=target.id)
    except Exception:
        return []
    for other in queryset:
        alias = other.sni or other.host
        if not alias or not _is_hostname(alias):
            continue
        other_address = _resolve_address(other.ip or other.host)
        if other_address == address and alias not in aliases:
            aliases.append(alias)
    return aliases


def _subject_alt_names_from_chain(der_chain: list[bytes]) -> list[str]:
    if not der_chain:
        return []
    parsed = _parse_certificate_der(der_chain[0])
    return [name for name in parsed.get("subject_alt_names", []) if _is_hostname(name)]


def _openssl_certificate_chain(target, timeout_sec: float, sni: str | None, starttls: str | None = None) -> list[bytes]:
    address = _target_address(target)
    cmd = ["openssl", "s_client", "-connect", f"{address}:{target.port}", "-showcerts"]
    if sni:
        cmd.extend(["-servername", sni])
    if starttls:
        cmd.extend(["-starttls", starttls])
    try:
        result = subprocess.run(
            cmd,
            input="",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=max(timeout_sec, 1.0) + 3.0,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    chain = []
    for pem in _extract_pem_certificates(result.stdout or ""):
        der = _pem_to_der(pem)
        if der:
            chain.append(der)
    return chain


def _extract_pem_certificates(text: str) -> list[str]:
    return re.findall(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", text, flags=re.DOTALL)


def _pem_to_der(pem: str) -> bytes | None:
    with tempfile.NamedTemporaryFile("w", suffix=".pem") as cert_file:
        cert_file.write(pem)
        cert_file.flush()
        try:
            return subprocess.check_output(
                ["openssl", "x509", "-in", cert_file.name, "-outform", "DER"],
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return None


def _scan_ssh(target, timeout_sec: float) -> list[AssetCandidate]:
    candidates = []
    for line in _ssh_keyscan_lines(target, timeout_sec):
        candidate = _ssh_host_key_candidate(target, line)
        if candidate:
            candidates.append(candidate)
    if candidates:
        return candidates
    return [_ssh_policy_candidate(target)]


def _ssh_keyscan_lines(target, timeout_sec: float) -> list[str]:
    address = _target_address(target)
    timeout = str(max(1, int(timeout_sec)))
    cmd = ["ssh-keyscan", "-T", timeout, "-p", str(target.port), "-t", SSH_KEY_TYPES, address]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=max(timeout_sec, 1.0) + 3.0,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.strip() for line in (result.stdout or "").splitlines() if line.strip() and not line.startswith("#")]


def _ssh_host_key_candidate(target, line: str) -> AssetCandidate | None:
    fields = line.split()
    if len(fields) < 3:
        return None
    key_type = fields[1]
    try:
        blob = base64.b64decode(fields[2].encode("ascii"), validate=True)
    except ValueError:
        return None
    parsed = _parse_ssh_public_key_blob(key_type, blob)
    if not parsed:
        return None
    fingerprint = _ssh_fingerprint(blob)
    return AssetCandidate(
        target_id=target.id,
        scanner_kind="network",
        name=f"{target.host}:{target.port} SSH host key {parsed['algorithm']}",
        asset_type="ssh_host_key",
        algorithm=parsed["algorithm"],
        algorithm_family=parsed["algorithm_family"],
        bom_ref=f"network:ssh-host-key:{fingerprint}",
        metadata={
            "scanner": "network",
            "type": "ssh_host_key",
            "ssh_fingerprint": fingerprint,
        },
    )


def _parse_ssh_public_key_blob(key_type: str, blob: bytes) -> dict[str, str] | None:
    try:
        algorithm, offset = _read_ssh_string(blob, 0)
        algorithm_text = algorithm.decode("ascii")
        if algorithm_text == "ssh-rsa" or key_type.startswith("rsa-"):
            _exponent, offset = _read_ssh_mpint(blob, offset)
            modulus, _offset = _read_ssh_mpint(blob, offset)
            return {"algorithm": f"RSA-{modulus.bit_length()}", "algorithm_family": "RSA"}
        if algorithm_text.startswith("ecdsa-sha2-"):
            curve, _offset = _read_ssh_string(blob, offset)
            return {"algorithm": f"ECDSA-{_normalize_ssh_curve(curve.decode('ascii'))}", "algorithm_family": "ECDSA"}
        if algorithm_text == "ssh-ed25519":
            return {"algorithm": "Ed25519", "algorithm_family": "EdDSA"}
    except (ValueError, UnicodeDecodeError):
        return None
    return None


def _read_ssh_string(data: bytes, offset: int) -> tuple[bytes, int]:
    if offset + 4 > len(data):
        raise ValueError("truncated ssh string")
    length = struct.unpack("!I", data[offset : offset + 4])[0]
    start = offset + 4
    end = start + length
    if end > len(data):
        raise ValueError("truncated ssh string body")
    return data[start:end], end


def _read_ssh_mpint(data: bytes, offset: int) -> tuple[int, int]:
    raw, offset = _read_ssh_string(data, offset)
    return int.from_bytes(raw, "big", signed=False), offset


def _normalize_ssh_curve(curve: str) -> str:
    return {"nistp256": "P256", "nistp384": "P384", "nistp521": "P521"}.get(curve, curve)


def _ssh_fingerprint(blob: bytes) -> str:
    digest = base64.b64encode(sha256(blob).digest()).decode("ascii").rstrip("=")
    return f"SHA256:{digest}"


def _ssh_policy_candidate(target) -> AssetCandidate:
    return AssetCandidate(
        target_id=target.id,
        scanner_kind="network",
        name=f"{target.host}:{target.port} SSH protocol policy",
        asset_type="protocol",
        algorithm="SSH key exchange policy",
        algorithm_family="DH",
        bom_ref=f"network:ssh-policy:{stable_bom_ref(target.host, target.port)}",
    )


def _scan_ike(target, timeout_sec: float) -> list[AssetCandidate]:
    natt = target.port == 4500
    packet, initiator_spi = _build_ike_sa_init(natt=natt)
    address = _target_address(target)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(max(timeout_sec, 0.75))
            sock.sendto(packet, (address, target.port))
            response, _addr = sock.recvfrom(4096)
    except OSError:
        return [_protocol_policy_candidate(target, "IKE", "IKE no response")]
    offset = 4 if response.startswith(b"\x00\x00\x00\x00") else 0
    if len(response) < offset + 28 or response[offset : offset + 8] != initiator_spi:
        return [_protocol_policy_candidate(target, "IKE", "IKE response mismatch")]
    candidates = _parse_ike_response_candidates(target, response)
    return candidates or [_protocol_policy_candidate(target, "IKE", "IKE proposal unparsed")]


def _build_ike_sa_init(natt: bool) -> tuple[bytes, bytes]:
    initiator_spi = os.urandom(8)
    sa_payload = _ike_sa_payload()
    ke_payload = _ike_ke_payload()
    nonce_payload = _ike_nonce_payload()
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


def _ike_sa_payload() -> bytes:
    transforms = b"".join(
        [
            _ike_transform(more=True, transform_type=1, transform_id=12, attrs=struct.pack("!HH", 0x800E, 256)),
            _ike_transform(more=True, transform_type=2, transform_id=5),
            _ike_transform(more=True, transform_type=3, transform_id=12),
            _ike_transform(more=False, transform_type=4, transform_id=14),
        ]
    )
    proposal = struct.pack("!BBHBBBB", 0, 0, 8 + len(transforms), 1, 1, 0, 4) + transforms
    return struct.pack("!BBH", IKE_NEXT_PAYLOAD_KE, 0, 4 + len(proposal)) + proposal


def _ike_transform(more: bool, transform_type: int, transform_id: int, attrs: bytes = b"") -> bytes:
    next_transform = 3 if more else 0
    return struct.pack("!BBHBBH", next_transform, 0, 8 + len(attrs), transform_type, 0, transform_id) + attrs


def _ike_ke_payload() -> bytes:
    key_exchange_data = os.urandom(256)
    body = struct.pack("!HH", 14, 0) + key_exchange_data
    return struct.pack("!BBH", IKE_NEXT_PAYLOAD_NONCE, 0, 4 + len(body)) + body


def _ike_nonce_payload() -> bytes:
    nonce = os.urandom(32)
    return struct.pack("!BBH", 0, 0, 4 + len(nonce)) + nonce


def _parse_ike_response_candidates(target, response: bytes) -> list[AssetCandidate]:
    offset = 4 if response.startswith(b"\x00\x00\x00\x00") else 0
    if len(response) < offset + 28:
        return []
    next_payload = response[offset + 16]
    cursor = offset + 28
    candidates = []
    while next_payload and cursor + 4 <= len(response):
        payload_next, _flags, payload_length = struct.unpack("!BBH", response[cursor : cursor + 4])
        if payload_length < 4 or cursor + payload_length > len(response):
            break
        payload_body = response[cursor + 4 : cursor + payload_length]
        if next_payload == IKE_NEXT_PAYLOAD_SA:
            candidates.extend(_parse_ike_sa_candidates(target, payload_body))
        next_payload = payload_next
        cursor += payload_length
    return candidates


def _parse_ike_sa_candidates(target, body: bytes) -> list[AssetCandidate]:
    candidates = []
    cursor = 0
    proposal_index = 0
    while cursor + 8 <= len(body):
        _next_proposal, _reserved, proposal_length = struct.unpack("!BBH", body[cursor : cursor + 4])
        if proposal_length < 8 or cursor + proposal_length > len(body):
            break
        proposal_index += 1
        proposal = body[cursor : cursor + proposal_length]
        _proposal_num, _protocol_id, spi_size, _num_transforms = struct.unpack("!BBBB", proposal[4:8])
        transform_cursor = 8 + spi_size
        transform_index = 0
        while transform_cursor + 8 <= len(proposal):
            next_transform, _reserved, transform_length = struct.unpack("!BBH", proposal[transform_cursor : transform_cursor + 4])
            if transform_length < 8 or transform_cursor + transform_length > len(proposal):
                break
            transform_index += 1
            transform_body = proposal[transform_cursor : transform_cursor + transform_length]
            transform_type = transform_body[4]
            transform_id = struct.unpack("!H", transform_body[6:8])[0]
            attrs = transform_body[8:]
            algorithm = _ike_algorithm(transform_type, transform_id, attrs)
            if algorithm:
                candidates.append(_ike_transform_candidate(target, proposal_index, transform_index, transform_type, transform_id, algorithm))
            if next_transform == 0:
                break
            transform_cursor += transform_length
        cursor += proposal_length
    return candidates


def _ike_algorithm(transform_type: int, transform_id: int, attrs: bytes) -> str | None:
    if transform_type == 1:
        algorithm = IKE_ENCRYPTION.get(transform_id, f"ENCR-{transform_id}")
        key_length = _ike_key_length(attrs)
        if key_length and algorithm in {"AES-CBC", "AES-CTR"}:
            return f"{algorithm}-{key_length}"
        return algorithm
    if transform_type == 2:
        return IKE_PRF.get(transform_id, f"PRF-{transform_id}")
    if transform_type == 3:
        return IKE_INTEGRITY.get(transform_id, f"INTEG-{transform_id}")
    if transform_type == 4:
        return IKE_DH_GROUPS.get(transform_id, f"DH-GROUP-{transform_id}")
    return None


def _ike_key_length(attrs: bytes) -> int | None:
    cursor = 0
    while cursor + 4 <= len(attrs):
        attr_type_or_format, value_or_length = struct.unpack("!HH", attrs[cursor : cursor + 4])
        attr_type = attr_type_or_format & 0x7FFF
        fixed = bool(attr_type_or_format & 0x8000)
        if attr_type == 14 and fixed:
            return value_or_length
        if fixed:
            cursor += 4
        else:
            cursor += 4 + value_or_length
    return None


def _ike_transform_candidate(
    target,
    proposal_index: int,
    transform_index: int,
    transform_type: int,
    transform_id: int,
    algorithm: str,
) -> AssetCandidate:
    kind = IKE_TRANSFORM_TYPE.get(transform_type, "transform")
    asset_type = "key_agreement" if transform_type == 4 else "protocol"
    return AssetCandidate(
        target_id=target.id,
        scanner_kind="network",
        name=f"{target.host}:{target.port} IKE {kind} {algorithm}",
        asset_type=asset_type,
        algorithm=algorithm,
        algorithm_family=family_from_algorithm(algorithm),
        bom_ref=f"network:ike:{stable_bom_ref(target.host, target.port, proposal_index, transform_index, transform_type, transform_id, algorithm)}",
    )


def _certificate_candidate(target, der: bytes | None, source: str, sni: str | None = None, chain_index: int = 0) -> AssetCandidate:
    fingerprint = sha256(der or b"").hexdigest()
    parsed = _parse_certificate_der(der or b"")
    algorithm = parsed["algorithm"] or "X.509 certificate"
    family = parsed["algorithm_family"] or family_from_algorithm(algorithm)
    role = "leaf" if chain_index == 0 else f"chain-{chain_index}"
    sni_label = sni or target.sni or target.host
    return AssetCandidate(
        target_id=target.id,
        scanner_kind="network",
        name=f"{target.host}:{target.port} {sni_label} certificate {role}",
        asset_type="certificate",
        algorithm=algorithm,
        algorithm_family=family,
        bom_ref=f"network:{source}:cert:{sni_label}:{chain_index}:{fingerprint}",
        metadata={
            "scanner": "network",
            "type": "certificate",
            "fingerprint_sha256": fingerprint,
            "sni": sni_label,
            "chain_index": chain_index,
            "source": source,
            **_certificate_validity_metadata(parsed),
        },
    )


def _tls_version_candidate(target, result: TlsProbeResult) -> AssetCandidate:
    sni_label = result.sni or target.sni or target.host
    return AssetCandidate(
        target_id=target.id,
        scanner_kind="network",
        name=f"{target.host}:{target.port} {sni_label} TLS version policy",
        asset_type="protocol",
        algorithm=result.tls_version or "TLS",
        algorithm_family=family_from_algorithm(result.tls_version),
        bom_ref=f"network:tls-version:{stable_bom_ref(target.host, target.port, sni_label, result.tls_version)}",
    )


def _tls_cipher_candidate(target, result: TlsProbeResult, cipher_suite: str) -> AssetCandidate:
    sni_label = result.sni or target.sni or target.host
    observation = "negotiated" if cipher_suite == result.cipher_suite else "enumerated"
    return AssetCandidate(
        target_id=target.id,
        scanner_kind="network",
        name=f"{target.host}:{target.port} {sni_label} TLS cipher suite",
        asset_type="protocol",
        algorithm=cipher_suite,
        algorithm_family=family_from_algorithm(cipher_suite),
        bom_ref=f"network:tls-cipher:{stable_bom_ref(target.host, target.port, sni_label, cipher_suite)}",
        metadata={
            "scanner": "network",
            "type": "tls_cipher_suite",
            "sni": sni_label,
            "observation": observation,
            "supported_cipher_suites": list(result.supported_cipher_suites),
        },
    )


def _application_protocol_candidate(target, protocol: str, algorithm: str, sni: str | None = None) -> AssetCandidate:
    sni_label = sni or target.sni or target.host
    return AssetCandidate(
        target_id=target.id,
        scanner_kind="network",
        name=f"{target.host}:{target.port} {protocol} application protocol",
        asset_type="protocol",
        algorithm=algorithm,
        algorithm_family=family_from_algorithm(algorithm),
        bom_ref=f"network:application-protocol:{stable_bom_ref(target.host, target.port, sni_label, protocol, algorithm)}",
    )


def _protocol_policy_candidate(target, protocol: str, algorithm: str) -> AssetCandidate:
    return AssetCandidate(
        target_id=target.id,
        scanner_kind="network",
        name=f"{target.host}:{target.port} {protocol} policy",
        asset_type="protocol",
        algorithm=algorithm,
        algorithm_family=family_from_algorithm(algorithm),
        bom_ref=f"network:{protocol.casefold()}-policy:{stable_bom_ref(target.host, target.port, algorithm)}",
    )


def _tcp_fallback_candidate(target) -> AssetCandidate:
    return AssetCandidate(
        target_id=target.id,
        scanner_kind="network",
        name=f"{target.host}:{target.port} open TCP service",
        asset_type="protocol",
        algorithm="TCP open service",
        algorithm_family="",
        bom_ref=f"network:tcp-fallback:{stable_bom_ref(target.host, target.port, target.transport)}",
    )


def _parse_certificate_der(der: bytes) -> dict[str, object]:
    if not der:
        return {"algorithm": "", "algorithm_family": "", "subject_alt_names": []}
    with tempfile.NamedTemporaryFile(suffix=".der") as cert_file:
        cert_file.write(der)
        cert_file.flush()
        try:
            text = subprocess.check_output(
                ["openssl", "x509", "-inform", "DER", "-in", cert_file.name, "-noout", "-text"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return {"algorithm": "", "algorithm_family": "", "subject_alt_names": []}
    return _parse_openssl_certificate_text(text)


def _parse_openssl_certificate_text(text: str) -> dict[str, object]:
    subject_alt_names = _parse_subject_alt_names(text)
    if "Public Key Algorithm: rsaEncryption" in text:
        bits = _first_match(text, r"Public-Key: \((\d+) bit\)")
        algorithm = f"RSA-{bits}" if bits else "RSA"
        return _certificate_parse_result(text, algorithm, "RSA", subject_alt_names)
    if "Public Key Algorithm: id-ecPublicKey" in text:
        curve = _first_match(text, r"ASN1 OID: ([A-Za-z0-9-]+)") or _first_match(text, r"NIST CURVE: ([A-Za-z0-9-]+)")
        algorithm = f"ECDSA-{_normalize_curve(curve)}" if curve else "ECDSA"
        return _certificate_parse_result(text, algorithm, "ECDSA", subject_alt_names)
    if "PUBLIC KEY ALGORITHM: ED25519" in text.upper():
        return _certificate_parse_result(text, "Ed25519", "EdDSA", subject_alt_names)
    return _certificate_parse_result(text, "", "", subject_alt_names)


def _certificate_parse_result(text: str, algorithm: str, algorithm_family: str, subject_alt_names: list[str]) -> dict[str, object]:
    result = {"algorithm": algorithm, "algorithm_family": algorithm_family, "subject_alt_names": subject_alt_names}
    not_after = _first_match(text, r"Not After\s*:\s*(.+)")
    if not_after:
        result["not_after"] = not_after.strip()
        expires_at = _parse_openssl_time(not_after.strip())
        if expires_at:
            result["expires_at"] = expires_at.isoformat().replace("+00:00", "Z")
    return result


def _certificate_validity_metadata(parsed: dict[str, object]) -> dict:
    metadata = {}
    for key in ("not_after", "expires_at"):
        value = parsed.get(key)
        if value:
            metadata[key] = value
    return metadata


def _parse_openssl_time(value: str) -> datetime | None:
    for fmt in ("%b %d %H:%M:%S %Y %Z", "%b %d %H:%M:%S %Y GMT"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=dt_timezone.utc)
        except ValueError:
            continue
    return None


def _parse_subject_alt_names(text: str) -> list[str]:
    names = []
    for name in re.findall(r"DNS:([^,\s]+)", text):
        normalized = name.rstrip(".").lower()
        if normalized and normalized not in names:
            names.append(normalized)
    return names


def _first_match(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text)
    return match.group(1) if match else None


def _normalize_curve(curve: str | None) -> str:
    if not curve:
        return ""
    return {"prime256v1": "P-256", "secp384r1": "P-384", "secp521r1": "P-521"}.get(curve, curve)


def _target_address(target) -> str:
    return target.ip or target.host


def _is_hostname(value: str | None) -> bool:
    if not value:
        return False
    try:
        ipaddress.ip_address(value)
        return False
    except ValueError:
        return True


def _resolve_address(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return socket.gethostbyname(value)
    except OSError:
        return value
