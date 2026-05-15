import base64
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from host_scanners import run_host_scan  # noqa: E402


class HostScannerTests(unittest.TestCase):
    def setUp(self):
        self._env = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_ssh_userkey_scanner_extracts_authorized_key_algorithms(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "authorized_keys"
            path.write_text(
                "\n".join(
                    [
                        f"ssh-rsa {_b64(_ssh_rsa_blob(2048))} deploy",
                        f"ecdsa-sha2-nistp256 {_b64(_ssh_ecdsa_blob())} admin",
                        f"ssh-ed25519 {_b64(_ssh_ed25519_blob())} ops",
                    ]
                ),
                encoding="utf-8",
            )
            os.environ["AGENT_CAPABILITIES"] = "agent.ssh_userkey"
            os.environ["AGENT_SSH_USERKEY_PATHS"] = tmp

            result = run_host_scan(["agent.ssh_userkey"], {})

            self.assertEqual(result["errors"], [])
            self.assertEqual(result["findings"][0]["type"], "ssh_authorized_key")
            self.assertEqual(result["findings"][0]["algorithms"], ["RSA-2048", "ECDSA-P256", "Ed25519"])

    def test_app_config_scanner_extracts_jwks_algorithms(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "current.json"
            path.write_text('{"keys": [{"algorithm": "RSA-2048"}]}', encoding="utf-8")
            os.environ["AGENT_CAPABILITIES"] = "agent.app_config"
            os.environ["AGENT_APP_CONFIG_PATHS"] = str(path)

            result = run_host_scan(["agent.app_config"], {})

            self.assertEqual(result["errors"], [])
            self.assertEqual(result["findings"][0]["type"], "jwt_signing_key")
            self.assertEqual(result["findings"][0]["algorithms"], ["RSA-2048"])

    def test_app_config_scanner_extracts_nginx_tls_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nginx.conf"
            path.write_text(
                "\n".join(
                    [
                        "ssl_protocols TLSv1.2 TLSv1.3;",
                        "ssl_ciphers ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES128-GCM-SHA256;",
                        "ssl_certificate /etc/nginx/ssl/server.crt;",
                        "ssl_certificate_key /etc/nginx/ssl/server.key;",
                    ]
                ),
                encoding="utf-8",
            )
            os.environ["AGENT_CAPABILITIES"] = "agent.app_config"
            os.environ["AGENT_APP_CONFIG_PATHS"] = str(path)

            result = run_host_scan(["agent.app_config"], {})

            self.assertEqual(result["errors"], [])
            finding = result["findings"][0]
            self.assertEqual(finding["type"], "tls_config")
            self.assertEqual(finding["tls_versions"], ["TLSv1.2", "TLSv1.3"])
            self.assertEqual(finding["cipher_suites"], ["ECDHE-RSA-AES256-GCM-SHA384", "ECDHE-ECDSA-AES128-GCM-SHA256"])
            self.assertEqual(finding["certificate_paths"], ["/etc/nginx/ssl/server.crt"])
            self.assertEqual(finding["private_key_paths"], ["/etc/nginx/ssl/server.key"])
            self.assertEqual(finding["referenced_by"], ["/etc/nginx/ssl/server.key"])

    def test_app_config_scanner_extracts_postfix_tls_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "main.cf"
            path.write_text(
                "\n".join(
                    [
                        "smtpd_tls_mandatory_protocols = !SSLv2, !SSLv3, !TLSv1, TLSv1.2 TLSv1.3",
                        "smtpd_tls_mandatory_ciphers = high",
                        "smtpd_tls_cert_file = /etc/postfix/server.crt",
                        "smtpd_tls_key_file = /etc/postfix/server.key",
                    ]
                ),
                encoding="utf-8",
            )
            os.environ["AGENT_CAPABILITIES"] = "agent.app_config"
            os.environ["AGENT_APP_CONFIG_PATHS"] = str(path)

            result = run_host_scan(["agent.app_config"], {})

            self.assertEqual(result["errors"], [])
            finding = result["findings"][0]
            self.assertEqual(finding["tls_versions"], ["TLSv1.2", "TLSv1.3"])
            self.assertEqual(finding["disabled_protocols"], ["SSLv2", "SSLv3", "TLSv1"])
            self.assertEqual(finding["cipher_suites"], ["high"])
            self.assertEqual(finding["certificate_paths"], ["/etc/postfix/server.crt"])
            self.assertEqual(finding["private_key_paths"], ["/etc/postfix/server.key"])

    def test_app_config_scanner_extracts_apache_tls_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "apache2.conf"
            path.write_text(
                "\n".join(
                    [
                        "SSLProtocol -all +TLSv1.2 +TLSv1.3",
                        "SSLCipherSuite HIGH:!aNULL:!MD5",
                        "SSLCertificateFile /etc/apache2/server.crt",
                        "SSLCertificateKeyFile /etc/apache2/server.key",
                    ]
                ),
                encoding="utf-8",
            )
            os.environ["AGENT_CAPABILITIES"] = "agent.app_config"
            os.environ["AGENT_APP_CONFIG_PATHS"] = str(path)

            result = run_host_scan(["agent.app_config"], {})

            self.assertEqual(result["errors"], [])
            finding = result["findings"][0]
            self.assertEqual(finding["tls_versions"], ["TLSv1.2", "TLSv1.3"])
            self.assertEqual(finding["cipher_suites"], ["HIGH", "!aNULL", "!MD5"])
            self.assertEqual(finding["certificate_paths"], ["/etc/apache2/server.crt"])
            self.assertEqual(finding["private_key_paths"], ["/etc/apache2/server.key"])

    def test_keystore_scanner_extracts_metadata_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "server.jks"
            path.write_text('{"type": "java_keystore", "format": "JKS", "algorithm": "RSA-1024"}', encoding="utf-8")
            os.environ["AGENT_CAPABILITIES"] = "agent.keystore"
            os.environ["AGENT_KEYSTORE_PATHS"] = tmp

            result = run_host_scan(["agent.keystore"], {})

            self.assertEqual(result["errors"], [])
            self.assertEqual(result["findings"][0]["type"], "java_keystore")
            self.assertEqual(result["findings"][0]["algorithm"], "RSA-1024")

    def test_private_key_scanner_reports_fingerprint_without_key_material(self):
        with tempfile.TemporaryDirectory() as tmp:
            key_path = Path(tmp) / "unused.key"
            subprocess.run(["openssl", "genrsa", "-out", str(key_path), "2048"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.environ["AGENT_CAPABILITIES"] = "agent.private_key_files"
            os.environ["AGENT_PRIVATE_KEY_PATHS"] = tmp

            result = run_host_scan(["agent.private_key_files"], {})

            self.assertEqual(result["errors"], [])
            finding = result["findings"][0]
            self.assertEqual(finding["type"], "dormant_private_key")
            self.assertEqual(finding["algorithm"], "RSA-2048")
            self.assertEqual(finding["key_size_bits"], 2048)
            self.assertEqual(len(finding["fingerprint_sha256"]), 64)
            self.assertNotIn("private_key", finding)
            self.assertTrue(finding["dormant"])

    def test_private_key_scanner_marks_config_referenced_key_in_use(self):
        with tempfile.TemporaryDirectory() as tmp:
            key_path = Path(tmp) / "server.key"
            conf_path = Path(tmp) / "nginx.conf"
            subprocess.run(["openssl", "genrsa", "-out", str(key_path), "2048"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            conf_path.write_text(f"ssl_certificate_key {key_path};\n", encoding="utf-8")
            os.environ["AGENT_CAPABILITIES"] = "agent.private_key_files"
            os.environ["AGENT_PRIVATE_KEY_PATHS"] = tmp
            os.environ["AGENT_REFERENCE_CONFIG_PATHS"] = str(conf_path)

            result = run_host_scan(["agent.private_key_files"], {})

            self.assertEqual(result["errors"], [])
            finding = result["findings"][0]
            self.assertEqual(finding["type"], "private_key_file")
            self.assertFalse(finding["dormant"])
            self.assertEqual(finding["referenced_by"], [str(conf_path)])

    def test_unsupported_capability_is_reported(self):
        os.environ["AGENT_CAPABILITIES"] = "agent.ssh_config"

        result = run_host_scan(["agent.keystore"], {})

        self.assertEqual(result["findings"], [])
        self.assertEqual(result["errors"][0]["error"], "unsupported_capability")


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


if __name__ == "__main__":
    unittest.main()
