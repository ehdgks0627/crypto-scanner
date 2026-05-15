import os
from datetime import datetime, timezone
from pathlib import Path

from .crypto_utils import (
    algorithms_from_ssh_authorized_keys,
    configured_paths,
    extract_key_references_from_config,
    iter_files,
    parse_certificate_algorithm,
    parse_certificate_metadata,
    parse_jwks_algorithms,
    parse_pkcs12_algorithm,
    parse_private_key_metadata,
    parse_public_key_algorithm,
    parse_ssh_config_algorithms,
    parse_tls_config_policy,
    read_json_or_kv,
)


CAPABILITY_CERT_STORE = "agent.cert_store"
CAPABILITY_PKG_KEYRING = "agent.pkg_keyring"
CAPABILITY_SSH_USERKEY = "agent.ssh_userkey"
CAPABILITY_SSH_CONFIG = "agent.ssh_config"
CAPABILITY_KEYSTORE = "agent.keystore"
CAPABILITY_APP_CERT_FILES = "agent.app_cert_files"
CAPABILITY_PRIVATE_KEY_FILES = "agent.private_key_files"
CAPABILITY_APP_CONFIG = "agent.app_config"

CERT_SUFFIXES = (".crt", ".pem", ".cer")
PRIVATE_KEY_SUFFIXES = (".key", ".pem", ".pkcs8")
KEYSTORE_SUFFIXES = (".p12", ".pfx", ".jks", ".keystore")


def run_host_scan(requested_capabilities: list[str], options: dict | None = None) -> dict:
    options = options or {}
    started_at = _now()
    requested = requested_capabilities or _configured_capabilities()
    supported = set(_configured_capabilities())
    findings = []
    errors = []

    for capability in requested:
        if capability not in supported:
            errors.append({"capability": capability, "error": "unsupported_capability"})
            continue
        scanner = SCANNERS.get(capability)
        if not scanner:
            errors.append({"capability": capability, "error": "scanner_not_implemented"})
            continue
        try:
            scanner_findings, scanner_errors = scanner(options)
        except Exception as exc:
            errors.append({"capability": capability, "error": str(exc)})
            continue
        findings.extend(scanner_findings)
        errors.extend(scanner_errors)

    return {
        "hostname": os.getenv("AGENT_HOSTNAME", os.uname().nodename),
        "started_at": started_at,
        "finished_at": _now(),
        "status": "SUCCESS" if not any(error.get("fatal") for error in errors) else "PARTIAL",
        "capabilities": _configured_capabilities(),
        "findings": findings,
        "errors": errors,
    }


def _scan_cert_store(options: dict) -> tuple[list[dict], list[dict]]:
    paths = configured_paths(
        "AGENT_CERT_STORE_PATHS",
        _existing_defaults(["/etc/testbed/certs", "/etc/api-gateway/trust", "/etc/ssl/certs/ca-certificates.crt"]),
    )
    findings, errors = [], []
    for path in iter_files(paths, CERT_SUFFIXES, _max_files(options)):
        metadata = parse_certificate_metadata(path)
        if not metadata:
            errors.append({"capability": CAPABILITY_CERT_STORE, "path": str(path), "error": "certificate_parse_failed"})
            continue
        findings.append({"type": _cert_store_type(path), "path": str(path), **metadata})
    return findings, errors


def _scan_pkg_keyring(options: dict) -> tuple[list[dict], list[dict]]:
    paths = configured_paths(
        "AGENT_PKG_KEYRING_PATHS",
        _existing_defaults(["/etc/registry/cosign.pub", "/etc/apt/keyrings", "/etc/apk/keys", "/etc/pki/rpm-gpg"]),
    )
    findings, errors = [], []
    for path in iter_files(paths, (".pub", ".gpg", ".key", ""), _max_files(options)):
        algorithm = parse_public_key_algorithm(path)
        if not algorithm:
            errors.append({"capability": CAPABILITY_PKG_KEYRING, "path": str(path), "error": "key_parse_failed"})
            continue
        findings.append({"type": _pkg_key_type(path), "path": str(path), "algorithm": algorithm})
    return findings, errors


def _scan_ssh_userkey(options: dict) -> tuple[list[dict], list[dict]]:
    paths = configured_paths("AGENT_SSH_USERKEY_PATHS", _existing_defaults(["/home", "/root/.ssh"]))
    findings, errors = [], []
    for path in iter_files(paths, ("authorized_keys", ".pub"), _max_files(options)):
        algorithms = algorithms_from_ssh_authorized_keys(path)
        if not algorithms:
            errors.append({"capability": CAPABILITY_SSH_USERKEY, "path": str(path), "error": "ssh_key_parse_failed"})
            continue
        findings.append({"type": "ssh_authorized_key", "path": str(path), "algorithms": algorithms})
    return findings, errors


def _scan_ssh_config(options: dict) -> tuple[list[dict], list[dict]]:
    paths = configured_paths("AGENT_SSH_CONFIG_PATHS", _existing_defaults(["/etc/ssh/sshd_config"]))
    findings, errors = [], []
    for path in iter_files(paths, ("sshd_config", ".conf"), _max_files(options)):
        policy = parse_ssh_config_algorithms(path)
        if not policy:
            errors.append({"capability": CAPABILITY_SSH_CONFIG, "path": str(path), "error": "ssh_config_parse_failed"})
            continue
        finding = {"type": "ssh_config", "path": str(path), "policy": policy}
        if policy.get("KexAlgorithms"):
            finding["kex_algorithms"] = policy["KexAlgorithms"]
        findings.append(finding)
    return findings, errors


def _scan_keystore(options: dict) -> tuple[list[dict], list[dict]]:
    paths = configured_paths(
        "AGENT_KEYSTORE_PATHS",
        _existing_defaults(["/var/lib/postgresql/keystore.p12", "/var/lib/vault/transit", "/etc/backup", "/opt/legacy-java/conf"]),
    )
    findings, errors = [], []
    for path in iter_files(paths, (*KEYSTORE_SUFFIXES, "pqc-testbed", "encryption-key.metadata"), _max_files(options)):
        metadata = read_json_or_kv(path)
        finding_type = _keystore_type(path, metadata)
        algorithm = metadata.get("algorithm") or _keystore_algorithm(path)
        if not algorithm:
            errors.append({"capability": CAPABILITY_KEYSTORE, "path": str(path), "error": "keystore_metadata_unavailable"})
            continue
        findings.append({"type": finding_type, "path": str(path), "algorithm": str(algorithm), "format": metadata.get("format")})
    return findings, errors


def _scan_app_cert_files(options: dict) -> tuple[list[dict], list[dict]]:
    paths = configured_paths(
        "AGENT_APP_CERT_PATHS",
        _existing_defaults(["/etc/nginx/ssl", "/var/lib/postgresql/testbed-certs", "/etc/saml", "/etc/testbed/certs/service"]),
    )
    findings, errors = [], []
    for path in iter_files(paths, CERT_SUFFIXES + (".pem",), _max_files(options)):
        metadata = parse_certificate_metadata(path)
        if not metadata:
            errors.append({"capability": CAPABILITY_APP_CERT_FILES, "path": str(path), "error": "certificate_parse_failed"})
            continue
        findings.append({"type": _app_cert_type(path), "path": str(path), **metadata})
    return findings, errors


def _scan_private_key_files(options: dict) -> tuple[list[dict], list[dict]]:
    paths = configured_paths(
        "AGENT_PRIVATE_KEY_PATHS",
        _existing_defaults([
            "/etc/nginx/ssl",
            "/etc/testbed/certs",
            "/etc/testbed/db-certs",
            "/var/lib/postgresql/testbed-certs",
            "/etc/ssh",
            "/home",
            "/root/.ssh",
            "/etc/backup",
            "/opt/legacy-java/conf",
        ]),
    )
    referenced = _referenced_private_key_paths()
    findings, errors = [], []
    for path in iter_files(paths, PRIVATE_KEY_SUFFIXES, _max_files(options)):
        metadata = parse_private_key_metadata(path)
        if not metadata:
            errors.append({"capability": CAPABILITY_PRIVATE_KEY_FILES, "path": str(path), "error": "private_key_parse_failed"})
            continue
        path_text = str(path)
        referenced_by = referenced.get(path_text) or referenced.get(path.name) or []
        in_use = bool(referenced_by) or _is_default_ssh_host_key(path)
        findings.append(
            {
                "type": "private_key_file" if in_use else "dormant_private_key",
                "path": path_text,
                "algorithm": metadata["algorithm"],
                "key_size_bits": metadata.get("key_size_bits"),
                "fingerprint_sha256": metadata.get("fingerprint_sha256"),
                "in_use": in_use,
                "dormant": not in_use,
                "referenced_by": referenced_by,
            }
        )
    return findings, errors


def _scan_app_config(options: dict) -> tuple[list[dict], list[dict]]:
    paths = configured_paths(
        "AGENT_APP_CONFIG_PATHS",
        _existing_defaults([
            "/etc/nginx/nginx.conf",
            "/etc/nginx/conf.d",
            "/etc/apache2",
            "/etc/httpd",
            "/etc/postfix/main.cf",
            "/etc/testbed/postgresql.conf",
            "/etc/api-gateway/jwks/current.json",
            "/var/lib/oidc/jwks.json",
            "/opt/legacy-java/conf/tls.properties",
        ]),
    )
    findings, errors = [], []
    for path in iter_files(paths, (".conf", ".json", ".properties", "main.cf"), _max_files(options)):
        finding = _app_config_finding(path)
        if finding:
            findings.append(finding)
        else:
            errors.append({"capability": CAPABILITY_APP_CONFIG, "path": str(path), "error": "config_parse_failed"})
    return findings, errors


def _app_config_finding(path: Path) -> dict | None:
    path_text = str(path)
    if path.name.endswith(".conf") and "nginx" in path_text:
        return _tls_config_finding(path, "tls_config")
    if path.name in {"main.cf", "httpd.conf", "apache2.conf"} or "/conf.d/" in path_text:
        return _tls_config_finding(path, "tls_config")
    if path.name == "postgresql.conf":
        algorithm = parse_certificate_algorithm(Path("/var/lib/postgresql/testbed-certs/server.crt")) or "TLS config"
        finding = _tls_config_finding(path, "postgres_tls_config")
        if not finding:
            return None
        finding["algorithm"] = algorithm
        return finding
    if path.name == "current.json":
        algorithms = parse_jwks_algorithms(path)
        return {"type": "jwt_signing_key", "path": path_text, "algorithms": algorithms} if algorithms else None
    if path.name == "jwks.json":
        algorithms = parse_jwks_algorithms(path)
        return {"type": "oidc_jwks", "path": path_text, "algorithms": algorithms} if algorithms else None
    if path.name == "tls.properties":
        return _tls_config_finding(path, "tls_config")
    return None


def _tls_config_finding(path: Path, finding_type: str) -> dict | None:
    policy = parse_tls_config_policy(path)
    references = extract_key_references_from_config(path)
    if not policy and not references:
        return None

    finding = {
        "type": finding_type,
        "path": str(path),
        "referenced_by": references or policy.get("private_key_paths", []),
    }
    finding.update(policy)
    if policy.get("tls_versions"):
        finding["minimum_tls_version"] = policy["tls_versions"][0]
    elif not policy:
        finding["minimum_tls_version"] = "TLS config"
    return finding


def _cert_store_type(path: Path) -> str:
    if "/api-gateway/trust/" in str(path):
        return "mtls_trust_bundle"
    return "system_ca"


def _pkg_key_type(path: Path) -> str:
    if "/registry/" in str(path):
        return "container_image_signing_key"
    return "package_signing_key"


def _keystore_type(path: Path, metadata: dict) -> str:
    if metadata.get("type"):
        return str(metadata["type"])
    path_text = str(path)
    if "/vault/" in path_text:
        return "kms_key_reference"
    if "/backup/" in path_text:
        return "backup_encryption_key"
    if path.suffix == ".jks":
        return "java_keystore"
    return "keystore"


def _app_cert_type(path: Path) -> str:
    path_text = str(path)
    if path_text.endswith("/signing.crt"):
        return "saml_signing_certificate"
    if path_text.endswith("/encryption.crt"):
        return "saml_encryption_certificate"
    return "certificate_file"


def _keystore_algorithm(path: Path) -> str | None:
    if path.suffix.lower() in {".p12", ".pfx"}:
        return parse_pkcs12_algorithm(path)
    return None


def _configured_capabilities() -> list[str]:
    raw = os.getenv("AGENT_CAPABILITIES", "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _referenced_private_key_paths() -> dict[str, list[str]]:
    explicit = [item.strip() for item in os.getenv("AGENT_REFERENCED_KEY_PATHS", "").split(os.pathsep) if item.strip()]
    config_paths = configured_paths(
        "AGENT_REFERENCE_CONFIG_PATHS",
        _existing_defaults([
            "/etc/nginx/nginx.conf",
            "/etc/nginx/conf.d",
            "/etc/apache2",
            "/etc/httpd",
            "/etc/postfix/main.cf",
            "/etc/ssh/sshd_config",
            "/etc/testbed/postgresql.conf",
        ]),
    )
    references: dict[str, list[str]] = {}
    for value in explicit:
        references.setdefault(value, []).append("AGENT_REFERENCED_KEY_PATHS")
        references.setdefault(Path(value).name, []).append("AGENT_REFERENCED_KEY_PATHS")
    for config_path in iter_files(config_paths, ("sshd_config", ".conf", "main.cf"), max_files=100):
        for value in extract_key_references_from_config(config_path):
            references.setdefault(value, []).append(str(config_path))
            references.setdefault(Path(value).name, []).append(str(config_path))
    return references


def _is_default_ssh_host_key(path: Path) -> bool:
    return path.parent == Path("/etc/ssh") and path.name.startswith("ssh_host_") and path.name.endswith("_key")


def _existing_defaults(paths: list[str]) -> list[str]:
    existing = []
    for path in paths:
        try:
            if Path(path).exists():
                existing.append(path)
        except OSError:
            continue
    return existing


def _max_files(options: dict) -> int:
    return int(options.get("max_files_per_capability") or os.getenv("AGENT_MAX_FILES_PER_CAPABILITY", "200"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


SCANNERS = {
    CAPABILITY_CERT_STORE: _scan_cert_store,
    CAPABILITY_PKG_KEYRING: _scan_pkg_keyring,
    CAPABILITY_SSH_USERKEY: _scan_ssh_userkey,
    CAPABILITY_SSH_CONFIG: _scan_ssh_config,
    CAPABILITY_KEYSTORE: _scan_keystore,
    CAPABILITY_APP_CERT_FILES: _scan_app_cert_files,
    CAPABILITY_PRIVATE_KEY_FILES: _scan_private_key_files,
    CAPABILITY_APP_CONFIG: _scan_app_config,
}
