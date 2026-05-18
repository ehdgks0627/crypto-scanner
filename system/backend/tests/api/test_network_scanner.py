import base64
import struct
import subprocess
from types import SimpleNamespace

from apps.jobs.homepage_context import infer_homepage_context
from apps.jobs import network_scanner


def target(**overrides):
    values = {
        "id": 10,
        "host": "web.testbed.local",
        "ip": None,
        "port": 443,
        "protocol_hint": "TLS",
        "sni": None,
        "transport": "TCP",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_network_scanner_tls_records_sni_alias_chain_version_and_cipher(monkeypatch):
    probe_calls = []

    def fake_known_sni_aliases(_target):
        return ["web-ec.testbed.local"]

    def fake_tls_probe(_target, _timeout_sec, sni=None, starttls=None):
        probe_calls.append((sni, starttls))
        if sni == "web-ec.testbed.local":
            return network_scanner.TlsProbeResult(
                sni=sni,
                der_chain=[b"ecdsa-leaf", b"ecdsa-intermediate"],
                tls_version="TLSv1.3",
                cipher_suite="TLS_AES_128_GCM_SHA256",
                alpn="http/1.1",
                supported_cipher_suites=("TLS_AES_128_GCM_SHA256", "TLS_CHACHA20_POLY1305_SHA256"),
            )
        return network_scanner.TlsProbeResult(
            sni=sni,
            der_chain=[b"rsa-leaf", b"rsa-intermediate"],
            tls_version="TLSv1.2",
            cipher_suite="TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
            alpn="h2",
            supported_cipher_suites=("TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384", "TLS_DHE_RSA_WITH_AES_256_GCM_SHA384"),
        )

    def fake_parse_certificate_der(der):
        if der.startswith(b"ecdsa"):
            return {"algorithm": "ECDSA-P256", "algorithm_family": "ECDSA", "subject_alt_names": []}
        return {"algorithm": "RSA-2048", "algorithm_family": "RSA", "subject_alt_names": []}

    monkeypatch.setattr(network_scanner, "_known_sni_aliases", fake_known_sni_aliases)
    monkeypatch.setattr(network_scanner, "_tls_probe", fake_tls_probe)
    monkeypatch.setattr(network_scanner, "_parse_certificate_der", fake_parse_certificate_der)

    candidates = network_scanner.scan_network_target(target())

    assert probe_calls == [("web.testbed.local", None), ("web-ec.testbed.local", None)]
    assert {(item.asset_type, item.algorithm, item.algorithm_family) for item in candidates} >= {
        ("certificate", "RSA-2048", "RSA"),
        ("certificate", "ECDSA-P256", "ECDSA"),
        ("protocol", "TLSv1.2", ""),
        ("protocol", "TLSv1.3", ""),
        ("protocol", "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384", "RSA"),
        ("protocol", "TLS_DHE_RSA_WITH_AES_256_GCM_SHA384", "RSA"),
        ("protocol", "TLS_AES_128_GCM_SHA256", "AES"),
        ("protocol", "TLS_CHACHA20_POLY1305_SHA256", "ChaCha20"),
    }
    assert any("chain-1" in item.name for item in candidates)
    enumerated = [item for item in candidates if item.algorithm == "TLS_CHACHA20_POLY1305_SHA256"]
    assert enumerated[0].metadata["observation"] == "enumerated"
    assert enumerated[0].metadata["supported_cipher_suites"] == ["TLS_AES_128_GCM_SHA256", "TLS_CHACHA20_POLY1305_SHA256"]


def test_network_scanner_certificate_parser_records_expiration():
    parsed = network_scanner._parse_openssl_certificate_text(
        """
        Certificate:
            Data:
                Validity
                    Not Before: May  1 00:00:00 2026 GMT
                    Not After : Jun 15 12:30:00 2026 GMT
                Subject Public Key Info:
                    Public Key Algorithm: rsaEncryption
                        Public-Key: (2048 bit)
        """
    )

    assert parsed["algorithm"] == "RSA-2048"
    assert parsed["not_after"] == "Jun 15 12:30:00 2026 GMT"
    assert parsed["expires_at"] == "2026-06-15T12:30:00Z"


def test_network_scanner_mqtt_tls_records_application_protocol(monkeypatch):
    monkeypatch.setattr(network_scanner, "_known_sni_aliases", lambda _target: [])
    monkeypatch.setattr(
        network_scanner,
        "_tls_probe",
        lambda _target, _timeout_sec, sni=None, starttls=None: network_scanner.TlsProbeResult(
            sni=sni,
            der_chain=[],
            tls_version="TLSv1.3",
            cipher_suite="TLS_AES_256_GCM_SHA384",
            alpn=None,
        ),
    )

    candidates = network_scanner.scan_network_target(
        target(host="mqtt.testbed.local", port=8883, protocol_hint="TLS", sni="mqtt.testbed.local")
    )

    assert any(item.asset_type == "protocol" and item.algorithm == "MQTT over TLS" for item in candidates)


def test_network_scanner_tls_records_pqc_readiness_assets(monkeypatch):
    monkeypatch.setattr(network_scanner, "_known_sni_aliases", lambda _target: [])
    monkeypatch.setattr(
        network_scanner,
        "_tls_probe",
        lambda _target, _timeout_sec, sni=None, starttls=None: network_scanner.TlsProbeResult(
            sni=sni,
            der_chain=[],
            tls_version="TLSv1.3",
            cipher_suite="TLS_AES_256_GCM_SHA384",
            alpn="http/1.1",
            pqc_readiness={
                "pqc_enabled": True,
                "standard": "NIST FIPS 203/204",
                "implementation": "testbed-reference",
                "signature_algorithm": "ML-DSA-65",
                "kem_group": "ML-KEM-768",
                "hybrid_group": "X25519MLKEM768",
                "evidence_path": "/.well-known/pqc-readiness.json",
            },
        ),
    )

    candidates = network_scanner.scan_network_target(
        target(host="pqc-tls.testbed.local", port=443, protocol_hint="TLS", sni="pqc-tls.testbed.local")
    )

    assert {(item.asset_type, item.algorithm, item.algorithm_family) for item in candidates} >= {
        ("certificate", "ML-DSA-65", "ML-DSA"),
        ("key_agreement", "ML-KEM-768", "ML-KEM"),
        ("protocol", "X25519MLKEM768", "ML-KEM"),
    }
    signature = next(item for item in candidates if item.algorithm == "ML-DSA-65")
    assert signature.metadata["source"] == "tls-pqc-readiness"
    assert signature.metadata["pqc_role"] == "signature"


def test_homepage_context_infers_public_homepage_without_storing_body():
    result = infer_homepage_context(
        url="https://web.testbed.local:443/",
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=b"""
            <html>
              <head>
                <title>Customer Portal Login</title>
                <meta name="description" content="Sign in to view invoices, billing history, and account profile.">
              </head>
              <body>
                <h1>Customer portal</h1>
                <p>My account dashboard for order history and profile updates.</p>
              </body>
            </html>
        """,
    )

    assert result["service_role"] == "customer_portal"
    assert result["sensitivity"] == "high"
    assert result["criticality"] == "high"
    assert result["exposure"] == "public_internet"
    assert result["lifespan_years"] == 10
    evidence = result["homepage_inference"]
    assert evidence["source"] == "homepage"
    assert evidence["method"] == "html_keyword_inference"
    assert evidence["title"] == "Customer Portal Login"
    assert {"customer portal", "billing", "invoice", "profile"} <= set(evidence["signals"])
    assert "body" not in evidence


def test_network_scanner_homepage_scheme_is_limited_to_http_services():
    assert network_scanner._homepage_scheme(target(port=443, protocol_hint="TLS")) == "https"
    assert network_scanner._homepage_scheme(target(port=8443, protocol_hint="TLS")) == "https"
    assert network_scanner._homepage_scheme(target(port=8080, protocol_hint="UNKNOWN")) == "http"
    assert network_scanner._homepage_scheme(target(port=3306, protocol_hint="TLS")) is None


def test_network_scanner_ssh_keyscan_maps_rsa_ecdsa_and_ed25519(monkeypatch):
    stdout = "\n".join(
        [
            f"ssh.testbed.local ssh-rsa {_b64(_ssh_rsa_blob(2048))}",
            f"ssh.testbed.local ecdsa-sha2-nistp256 {_b64(_ssh_ecdsa_blob())}",
            f"ssh.testbed.local ssh-ed25519 {_b64(_ssh_ed25519_blob())}",
        ]
    )

    def fake_run(cmd, **kwargs):
        assert cmd[:2] == ["ssh-keyscan", "-T"]
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    candidates = network_scanner.scan_network_target(target(host="ssh.testbed.local", port=22, protocol_hint="SSH"))

    assert {(item.asset_type, item.algorithm, item.algorithm_family) for item in candidates} == {
        ("ssh_host_key", "RSA-2048", "RSA"),
        ("ssh_host_key", "ECDSA-P256", "ECDSA"),
        ("ssh_host_key", "Ed25519", "EdDSA"),
    }


def test_network_scanner_ike_response_parser_maps_selected_transforms():
    response = _ike_response(
        [
            _ike_transform(1, 12, attrs=struct.pack("!HH", 0x800E, 256)),
            _ike_transform(2, 5),
            _ike_transform(3, 12),
            _ike_transform(4, 31),
        ]
    )

    candidates = network_scanner._parse_ike_response_candidates(
        target(host="ipsec.testbed.local", port=500, protocol_hint="IKE", transport="UDP"),
        response,
    )

    assert {(item.asset_type, item.algorithm, item.algorithm_family) for item in candidates} == {
        ("protocol", "AES-CBC-256", "AES"),
        ("protocol", "HMAC-SHA2-256", "HMAC"),
        ("protocol", "HMAC-SHA2-256-128", "HMAC"),
        ("key_agreement", "Curve25519", "ECDH"),
    }


def test_network_scanner_unknown_endpoint_emits_tcp_fallback_asset(monkeypatch):
    monkeypatch.setattr(network_scanner, "_scan_tls", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("no tls")))
    monkeypatch.setattr(network_scanner, "_scan_ssh", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("no ssh")))

    candidates = network_scanner.scan_network_target(target(host="unknown.testbed.local", port=12345, protocol_hint="UNKNOWN"))

    assert len(candidates) == 1
    assert candidates[0].asset_type == "protocol"
    assert candidates[0].algorithm == "TCP open service"


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _ssh_string(value: bytes) -> bytes:
    return struct.pack("!I", len(value)) + value


def _ssh_mpint(value: int) -> bytes:
    data = value.to_bytes((value.bit_length() + 7) // 8, "big")
    if data and data[0] & 0x80:
        data = b"\x00" + data
    return struct.pack("!I", len(data)) + data


def _ssh_rsa_blob(bits: int) -> bytes:
    modulus = (1 << (bits - 1)) + 65537
    return _ssh_string(b"ssh-rsa") + _ssh_mpint(65537) + _ssh_mpint(modulus)


def _ssh_ecdsa_blob() -> bytes:
    return (
        _ssh_string(b"ecdsa-sha2-nistp256")
        + _ssh_string(b"nistp256")
        + _ssh_string(b"\x04" + b"\x11" * 64)
    )


def _ssh_ed25519_blob() -> bytes:
    return _ssh_string(b"ssh-ed25519") + _ssh_string(b"\x22" * 32)


def _ike_transform(transform_type: int, transform_id: int, attrs: bytes = b"") -> tuple[int, int, bytes]:
    return transform_type, transform_id, attrs


def _ike_response(transforms: list[tuple[int, int, bytes]]) -> bytes:
    transform_bytes = b""
    for index, (transform_type, transform_id, attrs) in enumerate(transforms):
        next_transform = 3 if index < len(transforms) - 1 else 0
        transform_bytes += struct.pack("!BBHBBH", next_transform, 0, 8 + len(attrs), transform_type, 0, transform_id) + attrs
    proposal = struct.pack("!BBHBBBB", 0, 0, 8 + len(transform_bytes), 1, 1, 0, len(transforms)) + transform_bytes
    sa_payload = struct.pack("!BBH", 0, 0, 4 + len(proposal)) + proposal
    header = struct.pack(
        "!8s8sBBBBII",
        b"\x01" * 8,
        b"\x02" * 8,
        33,
        0x20,
        34,
        0x20,
        0,
        28 + len(sa_payload),
    )
    return header + sa_payload
