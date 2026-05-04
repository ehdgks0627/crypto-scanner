import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


LOG_LEVEL = os.getenv("AGENT_LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("testbed-agent")


def capabilities() -> list[str]:
    raw = os.getenv("AGENT_CAPABILITIES", "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def static_findings() -> list[dict]:
    hostname = os.getenv("AGENT_HOSTNAME", os.uname().nodename)
    if hostname == "web.testbed.local":
        return [
            {
                "type": "certificate_file",
                "path": "/etc/nginx/ssl/legacy-rsa1024.pem",
                "algorithm": "RSA-1024",
                "status": "unused",
            },
            {
                "type": "system_ca",
                "path": "/etc/testbed/certs/web/ca.crt",
                "algorithm": "RSA-4096",
            },
        ]
    if hostname == "ssh.testbed.local":
        return [
            {
                "type": "ssh_authorized_key",
                "path": "/home/testbed/.ssh/authorized_keys",
                "algorithms": ["RSA-2048", "ECDSA-P256", "Ed25519"],
            },
            {
                "type": "ssh_config",
                "path": "/etc/ssh/sshd_config",
                "kex_algorithms": ["curve25519-sha256", "ecdh-sha2-nistp256", "diffie-hellman-group14-sha256"],
            },
        ]
    if hostname == "db.testbed.local":
        return [
            {
                "type": "postgres_tls_config",
                "path": "/etc/testbed/postgresql.conf",
                "certificate": "/var/lib/postgresql/testbed-certs/server.crt",
                "algorithm": "RSA-1024",
            },
            {
                "type": "keystore",
                "path": "/var/lib/postgresql/keystore.p12",
                "algorithm": "RSA-1024",
                "format": "PKCS#12",
            }
        ]
    enterprise_findings = {
        "api-gateway.testbed.local": [
            {
                "type": "jwt_signing_key",
                "path": "/etc/api-gateway/jwks/current.json",
                "algorithm": "RSA-2048",
                "status": "active",
            },
            {
                "type": "mtls_trust_bundle",
                "path": "/etc/api-gateway/trust/internal-ca.pem",
                "algorithm": "RSA-4096",
            },
        ],
        "auth-oidc.testbed.local": [
            {
                "type": "oidc_jwks",
                "path": "/var/lib/oidc/jwks.json",
                "algorithms": ["RSA-2048", "ECDSA-P256"],
            }
        ],
        "saml-idp.testbed.local": [
            {
                "type": "saml_signing_certificate",
                "path": "/etc/saml/signing.crt",
                "algorithm": "RSA-2048",
            },
            {
                "type": "saml_encryption_certificate",
                "path": "/etc/saml/encryption.crt",
                "algorithm": "RSA-2048",
            },
        ],
        "container-registry.testbed.local": [
            {
                "type": "container_image_signing_key",
                "path": "/etc/registry/cosign.pub",
                "algorithm": "ECDSA-P256",
            }
        ],
        "vault.testbed.local": [
            {
                "type": "kms_key_reference",
                "path": "/var/lib/vault/transit/pqc-testbed",
                "algorithm": "RSA-4096",
                "status": "managed",
            }
        ],
        "backup-service.testbed.local": [
            {
                "type": "backup_encryption_key",
                "path": "/etc/backup/encryption-key.metadata",
                "algorithm": "RSA-2048",
                "lifespan_years": 10,
            }
        ],
        "legacy-java-app.testbed.local": [
            {
                "type": "java_keystore",
                "path": "/opt/legacy-java/conf/server.jks",
                "algorithm": "RSA-1024",
                "format": "JKS",
            },
            {
                "type": "tls_config",
                "path": "/opt/legacy-java/conf/tls.properties",
                "minimum_tls_version": "TLSv1.2",
            },
        ],
    }
    if hostname in enterprise_findings:
        return enterprise_findings[hostname]
    return []


class State:
    agent_id: str | None = None
    agent_token: str | None = None
    started_at = time.monotonic()


def request_json(method: str, url: str, payload: dict | None = None, headers: dict | None = None) -> tuple[int, dict]:
    body = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Content-Type": "application/json",
            **(headers or {}),
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        data = response.read()
        return response.status, json.loads(data.decode("utf-8") or "{}")


def register_loop() -> None:
    backend_url = os.getenv("BACKEND_URL", "http://host.docker.internal:8000").rstrip("/")
    bootstrap_token = os.getenv("BOOTSTRAP_TOKEN", "")
    hostname = os.getenv("AGENT_HOSTNAME", os.uname().nodename)
    agent_url = os.getenv("AGENT_URL", f"http://{hostname}:9100")
    payload = {
        "hostname": hostname,
        "agent_url": agent_url,
        "capabilities": capabilities(),
        "os_distribution": os.getenv("AGENT_OS_DISTRIBUTION", "testbed-container"),
    }
    headers = {"X-Bootstrap-Token": bootstrap_token}

    while True:
        try:
            status, response = request_json("POST", f"{backend_url}/api/agents/register", payload, headers)
            if status in {200, 201}:
                State.agent_id = response.get("id")
                State.agent_token = response.get("agent_token") or State.agent_token
                LOGGER.info("registered agent hostname=%s id=%s", hostname, State.agent_id)
                return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            LOGGER.warning("agent registration failed: %s", exc)
        time.sleep(5)


def heartbeat_loop() -> None:
    backend_url = os.getenv("BACKEND_URL", "http://host.docker.internal:8000").rstrip("/")
    while True:
        if State.agent_id and State.agent_token:
            try:
                request_json(
                    "POST",
                    f"{backend_url}/api/agents/{State.agent_id}/heartbeat",
                    {},
                    {"Authorization": f"Bearer {State.agent_token}"},
                )
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                LOGGER.warning("agent heartbeat failed: %s", exc)
        time.sleep(60)


class Handler(BaseHTTPRequestHandler):
    def _authorized(self) -> bool:
        expected_token = State.agent_token
        if not expected_token:
            return False
        return self.headers.get("Authorization") == f"Bearer {expected_token}"

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._send_json(
                200,
                {
                    "status": "ok",
                    "agent_id": State.agent_id,
                    "uptime_sec": int(time.monotonic() - State.started_at),
                },
            )
            return
        if self.path == "/capabilities":
            if not self._authorized():
                self._send_json(401, {"error": "invalid_token"})
                return
            self._send_json(200, {"capabilities": capabilities()})
            return
        self._send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path == "/scan":
            if not self._authorized():
                self._send_json(401, {"error": "invalid_token"})
                return
            self._send_json(
                200,
                {
                    "hostname": os.getenv("AGENT_HOSTNAME", os.uname().nodename),
                    "capabilities": capabilities(),
                    "findings": static_findings(),
                },
            )
            return
        self._send_json(404, {"error": "not_found"})

    def log_message(self, fmt: str, *args) -> None:
        LOGGER.debug(fmt, *args)


def main() -> None:
    host, port = os.getenv("AGENT_LISTEN", "0.0.0.0:9100").rsplit(":", 1)
    threading.Thread(target=register_loop, daemon=True).start()
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    server = ThreadingHTTPServer((host, int(port)), Handler)
    LOGGER.info("agent listening on %s:%s", host, port)
    server.serve_forever()


if __name__ == "__main__":
    main()
