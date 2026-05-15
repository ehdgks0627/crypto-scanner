import json
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.agents.models import Agent
from apps.assets.models import Asset, AssetContextOverride, AssetDependency, QualitativeAssessment
from apps.discoveries.models import DiscoveredEndpoint, Discovery
from apps.jobs.models import AsyncJob, ScanJob, ScanRunLog
from apps.performance import services as performance_services
from apps.risk.models import RiskScore, RiskWeights
from apps.snapshots.models import CbomSnapshot
from apps.targets.models import Target


SCENARIO = "testbed_demo"
SERIAL_PREFIX = "testbed-demo"


@dataclass(frozen=True)
class DemoAsset:
    target_key: tuple[str, int, str]
    name: str
    asset_type: str
    bom_ref: str
    algorithm: str
    algorithm_family: str
    score: float
    tier: str
    factors: dict


TARGET_FIXTURE = Path(settings.BASE_DIR) / "fixtures/initial_targets.json"
SCAN_SCANNERS = [
    "network",
    "agent.cert_store",
    "agent.ssh_userkey",
    "agent.ssh_config",
    "agent.keystore",
    "agent.pkg_keyring",
    "agent.app_cert_files",
    "agent.private_key_files",
    "agent.app_config",
]
DISCOVERY_PORTS = [22, 25, 443, 465, 587, 993, 995, 500, 2222, 3306, 4500, 5000, 5432, 6380, 8200, 8443, 8883, 9090, 9093, 9200, 9443, 15017]
AGENT_FIXTURES = [
    ("web.testbed.local", ["agent.cert_store", "agent.app_cert_files", "agent.private_key_files", "agent.app_config"], "Ubuntu 24.04", True),
    ("ssh.testbed.local", ["agent.ssh_userkey", "agent.ssh_config", "agent.private_key_files", "agent.pkg_keyring"], "Ubuntu 24.04", True),
    ("db.testbed.local", ["agent.cert_store", "agent.keystore", "agent.private_key_files", "agent.pkg_keyring"], "Debian 12", True),
    ("api-gateway.testbed.local", ["agent.cert_store", "agent.app_config", "agent.keystore"], "Ubuntu 24.04", True),
    ("auth-oidc.testbed.local", ["agent.cert_store", "agent.app_config", "agent.keystore"], "Ubuntu 24.04", True),
    ("saml-idp.testbed.local", ["agent.cert_store", "agent.app_config"], "Ubuntu 24.04", True),
    ("container-registry.testbed.local", ["agent.cert_store", "agent.pkg_keyring", "agent.app_config"], "Ubuntu 24.04", True),
    ("vault.testbed.local", ["agent.cert_store", "agent.keystore", "agent.app_config"], "Ubuntu 24.04", True),
    ("backup-service.testbed.local", ["agent.cert_store", "agent.keystore", "agent.app_config"], "Debian 12", True),
    ("legacy-java-app.testbed.local", ["agent.cert_store", "agent.keystore", "agent.app_config"], "RHEL 8", True),
]
DISCOVERY_AGENT_HOSTNAME = "probe.dmz.testbed.local"


LATEST_ASSETS = [
    DemoAsset(("web.testbed.local", 443, "TCP"), "web.testbed.local TLS leaf certificate", "certificate", "tls:web:leaf:rsa", "RSA-2048", "RSA", 82, "HIGH", {"a": 8, "d": 7, "e": 6, "l": 7, "c": 7}),
    DemoAsset(("web.testbed.local", 443, "TCP"), "web.testbed.local intermediate CA", "certificate", "tls:web:intermediate:rsa", "RSA-4096", "RSA", 78, "HIGH", {"a": 8, "d": 6, "e": 6, "l": 7, "c": 6}),
    DemoAsset(("web.testbed.local", 443, "TCP"), "nginx TLS cipher suite", "configuration", "tls:web:cipher-suite", "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384", "RSA", 71, "HIGH", {"a": 7, "d": 5, "e": 7, "l": 6, "c": 6}),
    DemoAsset(("web-ec.testbed.local", 443, "TCP"), "web-ec.testbed.local ECDSA leaf certificate", "certificate", "tls:web-ec:leaf:ecdsa", "ECDSA-P256", "ECDSA", 76, "HIGH", {"a": 7, "d": 6, "e": 6, "l": 6, "c": 6}),
    DemoAsset(("pqc-tls.testbed.local", 443, "TCP"), "pqc-tls.testbed.local ML-DSA certificate", "certificate", "tls:pqc:leaf:mldsa", "ML-DSA-65", "ML-DSA", 18, "LOW", {"a": 2, "d": 2, "e": 3, "l": 2, "c": 2}),
    DemoAsset(("pqc-tls.testbed.local", 443, "TCP"), "pqc-tls.testbed.local key agreement", "key_agreement", "tls:pqc:kem:mlkem", "ML-KEM-768", "ML-KEM", 16, "LOW", {"a": 2, "d": 2, "e": 3, "l": 1, "c": 2}),
    DemoAsset(("ssh.testbed.local", 22, "TCP"), "ssh.testbed.local host RSA key", "ssh_host_key", "ssh:host:rsa", "RSA-3072", "RSA", 88, "CRITICAL", {"a": 9, "d": 8, "e": 7, "l": 8, "c": 8}),
    DemoAsset(("ssh.testbed.local", 22, "TCP"), "ssh.testbed.local deploy user key", "ssh_user_key", "ssh:user:deploy:rsa", "RSA-2048", "RSA", 84, "HIGH", {"a": 8, "d": 8, "e": 6, "l": 7, "c": 7}),
    DemoAsset(("ssh.testbed.local", 22, "TCP"), "ssh.testbed.local admin ECDSA key", "ssh_user_key", "ssh:user:admin:ecdsa", "ECDSA-P256", "ECDSA", 81, "HIGH", {"a": 8, "d": 7, "e": 6, "l": 7, "c": 7}),
    DemoAsset(("mqtt.testbed.local", 8883, "TCP"), "mqtt.testbed.local device broker certificate", "certificate", "tls:mqtt:leaf:rsa", "RSA-2048", "RSA", 79, "HIGH", {"a": 8, "d": 7, "e": 5, "l": 7, "c": 7}),
    DemoAsset(("ipsec.testbed.local", 500, "UDP"), "ipsec.testbed.local IKE DH group", "key_agreement", "ike:site-vpn:dh14", "MODP-2048", "DH", 91, "CRITICAL", {"a": 9, "d": 8, "e": 8, "l": 8, "c": 9}),
    DemoAsset(("ipsec.testbed.local", 4500, "UDP"), "ipsec.testbed.local NAT-T integrity profile", "configuration", "ike:natt:integrity", "HMAC-SHA256", "HMAC", 34, "LOW", {"a": 3, "d": 3, "e": 5, "l": 3, "c": 3}),
    DemoAsset(("mail.testbed.local", 25, "TCP"), "mail.testbed.local SMTP STARTTLS certificate", "certificate", "smtp:starttls:leaf:rsa", "RSA-2048", "RSA", 73, "HIGH", {"a": 7, "d": 6, "e": 7, "l": 6, "c": 6}),
    DemoAsset(("mail.testbed.local", 465, "TCP"), "mail.testbed.local SMTPS certificate", "certificate", "smtp:smtps:leaf:rsa", "RSA-2048", "RSA", 72, "HIGH", {"a": 7, "d": 6, "e": 6, "l": 6, "c": 6}),
    DemoAsset(("mail.testbed.local", 587, "TCP"), "mail.testbed.local submission STARTTLS certificate", "certificate", "smtp:submission:leaf:rsa", "RSA-2048", "RSA", 71, "HIGH", {"a": 7, "d": 6, "e": 6, "l": 6, "c": 6}),
    DemoAsset(("mail.testbed.local", 993, "TCP"), "mail.testbed.local IMAPS certificate", "certificate", "imap:imaps:leaf:rsa", "RSA-2048", "RSA", 69, "MEDIUM", {"a": 7, "d": 5, "e": 5, "l": 6, "c": 6}),
    DemoAsset(("mail.testbed.local", 995, "TCP"), "mail.testbed.local POP3S certificate", "certificate", "pop3:pop3s:leaf:rsa", "RSA-2048", "RSA", 68, "MEDIUM", {"a": 7, "d": 5, "e": 5, "l": 6, "c": 5}),
    DemoAsset(("db.testbed.local", 5432, "TCP"), "db.testbed.local PostgreSQL TLS certificate", "certificate", "postgres:tls:leaf:rsa", "RSA-4096", "RSA", 93, "CRITICAL", {"a": 9, "d": 9, "e": 5, "l": 8, "c": 9}),
    DemoAsset(("db.testbed.local", 5432, "TCP"), "db.testbed.local application TLS policy", "configuration", "postgres:client:tls-policy", "TLS_VERIFY_CA_DISABLED", "UNKNOWN", 62, "MEDIUM", {"a": 5, "d": 6, "e": 4, "l": 6, "c": 6}),
    DemoAsset(("db.testbed.local", 5432, "TCP"), "db.testbed.local package signing key", "package_key", "postgres:apt:signing:rsa", "RSA-4096", "RSA", 80, "HIGH", {"a": 8, "d": 7, "e": 4, "l": 7, "c": 8}),
    DemoAsset(("db.testbed.local", 5432, "TCP"), "db.testbed.local JKS application key", "keystore_entry", "postgres:jks:app:rsa", "RSA-2048", "RSA", 86, "CRITICAL", {"a": 8, "d": 8, "e": 5, "l": 9, "c": 8}),
    DemoAsset(("api-gateway.testbed.local", 8443, "TCP"), "api-gateway.testbed.local TLS leaf certificate", "certificate", "tls:api-gateway:leaf:rsa", "RSA-3072", "RSA", 83, "HIGH", {"a": 8, "d": 7, "e": 8, "l": 7, "c": 8}),
    DemoAsset(("api-gateway.testbed.local", 8443, "TCP"), "api-gateway.testbed.local mTLS client CA", "certificate", "mtls:api-gateway:client-ca:ecdsa", "ECDSA-P384", "ECDSA", 74, "HIGH", {"a": 7, "d": 6, "e": 8, "l": 6, "c": 7}),
    DemoAsset(("api-gateway.testbed.local", 8443, "TCP"), "api-gateway.testbed.local JWT verification key", "configuration", "jwt:api-gateway:verify:rsa", "RSA-2048", "RSA", 82, "HIGH", {"a": 8, "d": 8, "e": 8, "l": 6, "c": 7}),
    DemoAsset(("admin-console.testbed.local", 443, "TCP"), "admin-console.testbed.local TLS leaf certificate", "certificate", "tls:admin-console:leaf:rsa", "RSA-4096", "RSA", 90, "CRITICAL", {"a": 9, "d": 8, "e": 7, "l": 8, "c": 9}),
    DemoAsset(("admin-console.testbed.local", 443, "TCP"), "admin-console.testbed.local session signing key", "configuration", "app:admin-console:session:hmac", "HMAC-SHA256", "HMAC", 36, "LOW", {"a": 3, "d": 4, "e": 6, "l": 3, "c": 3}),
    DemoAsset(("mobile-api.testbed.local", 443, "TCP"), "mobile-api.testbed.local TLS leaf certificate", "certificate", "tls:mobile-api:leaf:ecdsa", "ECDSA-P256", "ECDSA", 75, "HIGH", {"a": 7, "d": 6, "e": 8, "l": 6, "c": 7}),
    DemoAsset(("mobile-api.testbed.local", 443, "TCP"), "mobile-api.testbed.local certificate pin set", "configuration", "mobile:api:pinset:sha256", "SHA-256", "SHA", 28, "LOW", {"a": 2, "d": 3, "e": 8, "l": 2, "c": 2}),
    DemoAsset(("auth-oidc.testbed.local", 443, "TCP"), "auth-oidc.testbed.local TLS leaf certificate", "certificate", "tls:oidc:leaf:rsa", "RSA-4096", "RSA", 89, "CRITICAL", {"a": 9, "d": 8, "e": 7, "l": 8, "c": 9}),
    DemoAsset(("auth-oidc.testbed.local", 443, "TCP"), "auth-oidc.testbed.local ID token signing key", "keystore_entry", "oidc:id-token:signing:rsa", "RSA-2048", "RSA", 92, "CRITICAL", {"a": 9, "d": 9, "e": 7, "l": 8, "c": 9}),
    DemoAsset(("auth-oidc.testbed.local", 443, "TCP"), "auth-oidc.testbed.local JWE encryption key", "keystore_entry", "oidc:jwe:encryption:rsa", "RSA-OAEP-2048", "RSA", 85, "HIGH", {"a": 8, "d": 8, "e": 7, "l": 7, "c": 8}),
    DemoAsset(("saml-idp.testbed.local", 443, "TCP"), "saml-idp.testbed.local TLS leaf certificate", "certificate", "tls:saml-idp:leaf:ecdsa", "ECDSA-P256", "ECDSA", 77, "HIGH", {"a": 7, "d": 7, "e": 6, "l": 7, "c": 7}),
    DemoAsset(("saml-idp.testbed.local", 443, "TCP"), "saml-idp.testbed.local assertion signing key", "keystore_entry", "saml:assertion:signing:rsa", "RSA-2048", "RSA", 94, "CRITICAL", {"a": 9, "d": 9, "e": 6, "l": 9, "c": 9}),
    DemoAsset(("saml-idp.testbed.local", 443, "TCP"), "saml-idp.testbed.local assertion encryption key", "keystore_entry", "saml:assertion:encryption:rsa", "RSA-3072", "RSA", 88, "CRITICAL", {"a": 9, "d": 8, "e": 6, "l": 8, "c": 9}),
    DemoAsset(("mysql-legacy.testbed.local", 3306, "TCP"), "mysql-legacy.testbed.local TLS leaf certificate", "certificate", "tls:mysql-legacy:leaf:rsa", "RSA-2048", "RSA", 80, "HIGH", {"a": 8, "d": 7, "e": 5, "l": 7, "c": 8}),
    DemoAsset(("mysql-legacy.testbed.local", 3306, "TCP"), "mysql-legacy.testbed.local client CA", "certificate", "tls:mysql-legacy:client-ca:rsa", "RSA-4096", "RSA", 82, "HIGH", {"a": 8, "d": 8, "e": 5, "l": 7, "c": 8}),
    DemoAsset(("mysql-legacy.testbed.local", 3306, "TCP"), "mysql-legacy.testbed.local SSL mode policy", "configuration", "mysql:ssl-mode:verify-disabled", "TLS_VERIFY_IDENTITY_DISABLED", "UNKNOWN", 64, "MEDIUM", {"a": 5, "d": 7, "e": 5, "l": 6, "c": 6}),
    DemoAsset(("redis-cache.testbed.local", 6380, "TCP"), "redis-cache.testbed.local TLS leaf certificate", "certificate", "tls:redis-cache:leaf:rsa", "RSA-2048", "RSA", 72, "HIGH", {"a": 7, "d": 6, "e": 4, "l": 6, "c": 7}),
    DemoAsset(("redis-cache.testbed.local", 6380, "TCP"), "redis-cache.testbed.local cluster bus TLS profile", "configuration", "redis:cluster-bus:cipher:rsa", "TLS_RSA_WITH_AES_128_CBC_SHA", "RSA", 78, "HIGH", {"a": 8, "d": 6, "e": 4, "l": 7, "c": 8}),
    DemoAsset(("kafka-broker.testbed.local", 9093, "TCP"), "kafka-broker.testbed.local TLS leaf certificate", "certificate", "tls:kafka-broker:leaf:rsa", "RSA-4096", "RSA", 87, "CRITICAL", {"a": 9, "d": 8, "e": 4, "l": 8, "c": 9}),
    DemoAsset(("kafka-broker.testbed.local", 9093, "TCP"), "kafka-broker.testbed.local inter-broker client CA", "certificate", "mtls:kafka-broker:client-ca:rsa", "RSA-4096", "RSA", 83, "HIGH", {"a": 8, "d": 8, "e": 4, "l": 8, "c": 8}),
    DemoAsset(("kafka-broker.testbed.local", 9093, "TCP"), "kafka-broker.testbed.local SCRAM credential hash", "configuration", "kafka:scram:sha512", "HMAC-SHA512", "HMAC", 32, "LOW", {"a": 3, "d": 3, "e": 4, "l": 3, "c": 3}),
    DemoAsset(("internal-grpc.testbed.local", 8443, "TCP"), "internal-grpc.testbed.local TLS leaf certificate", "certificate", "tls:internal-grpc:leaf:ecdsa", "ECDSA-P256", "ECDSA", 74, "HIGH", {"a": 7, "d": 6, "e": 4, "l": 6, "c": 7}),
    DemoAsset(("internal-grpc.testbed.local", 8443, "TCP"), "internal-grpc.testbed.local service account token", "configuration", "grpc:service-account:hmac", "HMAC-SHA256", "HMAC", 48, "MEDIUM", {"a": 4, "d": 5, "e": 4, "l": 4, "c": 5}),
    DemoAsset(("service-mesh-mtls.testbed.local", 15017, "TCP"), "service-mesh-mtls.testbed.local root CA", "certificate", "mesh:root-ca:rsa", "RSA-4096", "RSA", 95, "CRITICAL", {"a": 10, "d": 9, "e": 5, "l": 9, "c": 10}),
    DemoAsset(("service-mesh-mtls.testbed.local", 15017, "TCP"), "service-mesh-mtls.testbed.local workload certificate", "certificate", "mesh:workload:leaf:ecdsa", "ECDSA-P256", "ECDSA", 78, "HIGH", {"a": 8, "d": 7, "e": 5, "l": 7, "c": 7}),
    DemoAsset(("service-mesh-mtls.testbed.local", 15017, "TCP"), "service-mesh-mtls.testbed.local SDS policy", "configuration", "mesh:sds:policy:unknown", "UNVERSIONED_TLS_POLICY", "UNKNOWN", 58, "MEDIUM", {"a": 5, "d": 6, "e": 5, "l": 5, "c": 5}),
    DemoAsset(("gitlab-runner.testbed.local", 9443, "TCP"), "gitlab-runner.testbed.local TLS leaf certificate", "certificate", "tls:gitlab-runner:leaf:rsa", "RSA-2048", "RSA", 76, "HIGH", {"a": 8, "d": 6, "e": 5, "l": 7, "c": 7}),
    DemoAsset(("gitlab-runner.testbed.local", 9443, "TCP"), "gitlab-runner.testbed.local job token signing key", "configuration", "ci:runner:job-token:hmac", "HMAC-SHA256", "HMAC", 52, "MEDIUM", {"a": 5, "d": 5, "e": 5, "l": 4, "c": 5}),
    DemoAsset(("container-registry.testbed.local", 5000, "TCP"), "container-registry.testbed.local TLS leaf certificate", "certificate", "tls:container-registry:leaf:ecdsa", "ECDSA-P384", "ECDSA", 74, "HIGH", {"a": 7, "d": 6, "e": 4, "l": 7, "c": 7}),
    DemoAsset(("container-registry.testbed.local", 5000, "TCP"), "container-registry.testbed.local image signing key", "package_key", "registry:image-signing:ecdsa", "ECDSA-P256", "ECDSA", 79, "HIGH", {"a": 8, "d": 7, "e": 4, "l": 7, "c": 8}),
    DemoAsset(("container-registry.testbed.local", 5000, "TCP"), "container-registry.testbed.local package signing key", "package_key", "registry:package-signing:rsa", "RSA-4096", "RSA", 86, "CRITICAL", {"a": 9, "d": 8, "e": 4, "l": 8, "c": 9}),
    DemoAsset(("artifact-repo.testbed.local", 8443, "TCP"), "artifact-repo.testbed.local TLS leaf certificate", "certificate", "tls:artifact-repo:leaf:rsa", "RSA-2048", "RSA", 77, "HIGH", {"a": 8, "d": 6, "e": 4, "l": 7, "c": 8}),
    DemoAsset(("artifact-repo.testbed.local", 8443, "TCP"), "artifact-repo.testbed.local repository signing key", "package_key", "artifact-repo:signing:rsa", "RSA-4096", "RSA", 84, "CRITICAL", {"a": 9, "d": 8, "e": 4, "l": 8, "c": 8}),
    DemoAsset(("vault.testbed.local", 8200, "TCP"), "vault.testbed.local TLS leaf certificate", "certificate", "tls:vault:leaf:ecdsa", "ECDSA-P384", "ECDSA", 75, "HIGH", {"a": 8, "d": 6, "e": 3, "l": 7, "c": 8}),
    DemoAsset(("vault.testbed.local", 8200, "TCP"), "vault.testbed.local transit RSA key", "keystore_entry", "vault:transit:rsa", "RSA-4096", "RSA", 91, "CRITICAL", {"a": 10, "d": 9, "e": 3, "l": 8, "c": 10}),
    DemoAsset(("vault.testbed.local", 8200, "TCP"), "vault.testbed.local unseal key shares", "keystore_entry", "vault:unseal:shares", "SHAMIR-5OF8", "UNKNOWN", 55, "MEDIUM", {"a": 5, "d": 6, "e": 3, "l": 5, "c": 6}),
    DemoAsset(("backup-service.testbed.local", 8443, "TCP"), "backup-service.testbed.local TLS leaf certificate", "certificate", "tls:backup-service:leaf:rsa", "RSA-4096", "RSA", 89, "CRITICAL", {"a": 9, "d": 8, "e": 3, "l": 8, "c": 9}),
    DemoAsset(("backup-service.testbed.local", 8443, "TCP"), "backup-service.testbed.local envelope encryption key", "keystore_entry", "backup:envelope:aes", "AES-256-GCM", "AES", 22, "LOW", {"a": 2, "d": 2, "e": 3, "l": 2, "c": 2}),
    DemoAsset(("backup-service.testbed.local", 8443, "TCP"), "backup-service.testbed.local key wrapping key", "keystore_entry", "backup:keywrap:rsa", "RSA-4096", "RSA", 90, "CRITICAL", {"a": 10, "d": 8, "e": 3, "l": 8, "c": 9}),
    DemoAsset(("monitoring.testbed.local", 9090, "TCP"), "monitoring.testbed.local TLS leaf certificate", "certificate", "tls:monitoring:leaf:ecdsa", "ECDSA-P256", "ECDSA", 61, "MEDIUM", {"a": 6, "d": 5, "e": 3, "l": 5, "c": 6}),
    DemoAsset(("monitoring.testbed.local", 9090, "TCP"), "monitoring.testbed.local alert webhook signing key", "configuration", "monitoring:webhook:hmac", "HMAC-SHA256", "HMAC", 35, "LOW", {"a": 3, "d": 4, "e": 3, "l": 3, "c": 3}),
    DemoAsset(("logging.testbed.local", 9200, "TCP"), "logging.testbed.local TLS leaf certificate", "certificate", "tls:logging:leaf:rsa", "RSA-2048", "RSA", 79, "HIGH", {"a": 8, "d": 7, "e": 4, "l": 7, "c": 7}),
    DemoAsset(("logging.testbed.local", 9200, "TCP"), "logging.testbed.local index encryption key", "keystore_entry", "logging:index:aes", "AES-256-GCM", "AES", 26, "LOW", {"a": 2, "d": 3, "e": 4, "l": 2, "c": 2}),
    DemoAsset(("legacy-java-app.testbed.local", 8443, "TCP"), "legacy-java-app.testbed.local TLS leaf certificate", "certificate", "tls:legacy-java-app:leaf:rsa", "RSA-2048", "RSA", 90, "CRITICAL", {"a": 9, "d": 8, "e": 4, "l": 9, "c": 9}),
    DemoAsset(("legacy-java-app.testbed.local", 8443, "TCP"), "legacy-java-app.testbed.local JKS application key", "keystore_entry", "legacy-java:jks:app:rsa1024", "RSA-1024", "RSA", 98, "CRITICAL", {"a": 10, "d": 10, "e": 4, "l": 10, "c": 10}),
    DemoAsset(("legacy-java-app.testbed.local", 8443, "TCP"), "legacy-java-app.testbed.local truststore CA", "certificate", "legacy-java:truststore:ca:sha1withrsa", "SHA1withRSA", "RSA", 87, "HIGH", {"a": 9, "d": 8, "e": 4, "l": 8, "c": 8}),
]

BASELINE_ASSETS = [
    asset for asset in LATEST_ASSETS
    if asset.bom_ref not in {"tls:pqc:leaf:mldsa", "tls:pqc:kem:mlkem", "postgres:client:tls-policy", "postgres:jks:app:rsa"}
]

DISCOVERY_ENDPOINTS = [
    ("172.20.10.11", 443, "TCP", "TLS", "TLS", True, ("web.testbed.local", 443, "TCP")),
    ("172.20.10.12", 443, "TCP", "TLS", "TLS", True, ("web-ec.testbed.local", 443, "TCP")),
    ("172.20.10.13", 443, "TCP", "TLS", "TLS", True, ("pqc-tls.testbed.local", 443, "TCP")),
    ("172.20.20.10", 22, "TCP", "SSH", "SSH", True, ("ssh.testbed.local", 22, "TCP")),
    ("172.20.30.10", 8883, "TCP", "MQTT over TLS", "TLS", True, ("mqtt.testbed.local", 8883, "TCP")),
    ("172.20.40.10", 500, "UDP", "IKEv2", "IKE", True, ("ipsec.testbed.local", 500, "UDP")),
    ("172.20.40.10", 4500, "UDP", "IKEv2 NAT-T", "IKE", True, ("ipsec.testbed.local", 4500, "UDP")),
    ("172.20.50.10", 25, "TCP", "SMTP STARTTLS", "SMTP", True, ("mail.testbed.local", 25, "TCP")),
    ("172.20.50.10", 465, "TCP", "SMTPS", "SMTP", True, ("mail.testbed.local", 465, "TCP")),
    ("172.20.50.10", 587, "TCP", "SMTP submission", "SMTP", True, ("mail.testbed.local", 587, "TCP")),
    ("172.20.50.10", 993, "TCP", "IMAPS", "IMAP", True, ("mail.testbed.local", 993, "TCP")),
    ("172.20.50.10", 995, "TCP", "POP3S", "POP3", True, ("mail.testbed.local", 995, "TCP")),
    ("172.20.60.10", 5432, "TCP", "PostgreSQL TLS", "UNKNOWN", True, ("db.testbed.local", 5432, "TCP")),
    ("172.20.60.11", 8443, "TCP", "TLS", "TLS", False, None),
    ("172.20.70.20", 2222, "TCP", "SSH", "SSH", False, None),
    ("172.20.10.20", 8443, "TCP", "TLS", "TLS", True, ("api-gateway.testbed.local", 8443, "TCP")),
    ("172.20.10.21", 443, "TCP", "TLS", "TLS", True, ("admin-console.testbed.local", 443, "TCP")),
    ("172.20.10.22", 443, "TCP", "TLS", "TLS", True, ("mobile-api.testbed.local", 443, "TCP")),
    ("172.20.20.20", 443, "TCP", "TLS", "TLS", True, ("auth-oidc.testbed.local", 443, "TCP")),
    ("172.20.20.21", 443, "TCP", "TLS", "TLS", True, ("saml-idp.testbed.local", 443, "TCP")),
    ("172.20.60.20", 3306, "TCP", "TLS", "TLS", True, ("mysql-legacy.testbed.local", 3306, "TCP")),
    ("172.20.60.21", 6380, "TCP", "TLS", "TLS", True, ("redis-cache.testbed.local", 6380, "TCP")),
    ("172.20.60.22", 9093, "TCP", "TLS", "TLS", True, ("kafka-broker.testbed.local", 9093, "TCP")),
    ("172.20.70.10", 8443, "TCP", "TLS", "TLS", True, ("internal-grpc.testbed.local", 8443, "TCP")),
    ("172.20.70.11", 15017, "TCP", "TLS", "TLS", True, ("service-mesh-mtls.testbed.local", 15017, "TCP")),
    ("172.20.80.10", 9443, "TCP", "TLS", "TLS", True, ("gitlab-runner.testbed.local", 9443, "TCP")),
    ("172.20.80.11", 5000, "TCP", "TLS", "TLS", True, ("container-registry.testbed.local", 5000, "TCP")),
    ("172.20.80.12", 8443, "TCP", "TLS", "TLS", True, ("artifact-repo.testbed.local", 8443, "TCP")),
    ("172.20.90.10", 8200, "TCP", "TLS", "TLS", True, ("vault.testbed.local", 8200, "TCP")),
    ("172.20.90.11", 8443, "TCP", "TLS", "TLS", True, ("backup-service.testbed.local", 8443, "TCP")),
    ("172.20.100.10", 9090, "TCP", "TLS", "TLS", True, ("monitoring.testbed.local", 9090, "TCP")),
    ("172.20.100.11", 9200, "TCP", "TLS", "TLS", True, ("logging.testbed.local", 9200, "TCP")),
    ("172.20.110.10", 8443, "TCP", "TLS", "TLS", True, ("legacy-java-app.testbed.local", 8443, "TCP")),
]

DEMO_DEPENDENCIES = [
    ("tls:web:leaf:rsa", "tls:web:intermediate:rsa", "certificate_chain"),
    ("tls:web:cipher-suite", "tls:web:leaf:rsa", "uses_certificate"),
    ("tls:web:cipher-suite", "tls:web:intermediate:rsa", "uses_certificate"),
    ("postgres:client:tls-policy", "postgres:tls:leaf:rsa", "protects_connection"),
    ("postgres:jks:app:rsa", "postgres:tls:leaf:rsa", "stores_key_material"),
]


class Command(BaseCommand):
    help = "Seed testbed scenario demo data for the UI."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing testbed demo data before seeding.")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            self._reset_demo()

        now = timezone.now()
        targets = self._seed_targets()
        self._seed_agents(now)
        scan_job = self._seed_scan_job(targets, now)
        baseline = self._seed_snapshot("baseline", BASELINE_ASSETS, targets, scan_job, now - timedelta(days=2, hours=4))
        latest = self._seed_snapshot("latest", LATEST_ASSETS, targets, scan_job, now - timedelta(minutes=35))
        self._seed_performance_runs(baseline, latest, now - timedelta(minutes=25))
        discovery = self._seed_discovery(targets, now - timedelta(hours=2))
        self._seed_recompute_job(latest, now - timedelta(minutes=12))
        self._seed_failed_scan_job(targets, now - timedelta(minutes=8))
        self._seed_cancelled_discovery(now - timedelta(minutes=4))
        RiskWeights.objects.update_or_create(
            id=1,
            defaults={"wA": 1.4, "wD": 1.2, "wE": 1.1, "wL": 1.3, "wC": 1.5},
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {SERIAL_PREFIX}: targets={len(targets)}, snapshots=2, latest_snapshot={latest.id}, "
                f"baseline_snapshot={baseline.id}, discovery={discovery.id}, jobs=5"
            )
        )

    def _reset_demo(self):
        CbomSnapshot.objects.filter(serial_number__startswith=SERIAL_PREFIX).delete()
        AsyncJob.objects.filter(request_payload__scenario=SCENARIO).delete()
        Discovery.objects.filter(cidr="172.20.0.0/16").delete()
        Agent.objects.filter(hostname__in=[*[hostname for hostname, *_ in AGENT_FIXTURES], DISCOVERY_AGENT_HOSTNAME]).delete()

    def _seed_targets(self):
        targets = {}
        for row in json.loads(TARGET_FIXTURE.read_text()):
            fields = row["fields"]
            target, _ = Target.objects.update_or_create(
                host=fields["host"],
                port=fields["port"],
                transport=fields["transport"],
                defaults={
                    "display_name": fields.get("display_name"),
                    "ip": fields["ip"],
                    "protocol_hint": fields["protocol_hint"],
                    "sni": fields["sni"],
                    "agent_enabled": fields["agent_enabled"],
                    "agent_url": fields["agent_url"],
                    "context": fields["context"],
                },
            )
            targets[(target.host, target.port, target.transport)] = target
        return targets

    def _seed_agents(self, now):
        for index, (hostname, capabilities, os_distribution, active) in enumerate(AGENT_FIXTURES):
            last_seen = now - timedelta(minutes=4 + (index * 7))
            Agent.objects.update_or_create(
                hostname=hostname,
                agent_role=Agent.ROLE_HOST,
                defaults={
                    "agent_url": f"https://{hostname}:9443",
                    "capabilities": capabilities,
                    "os_distribution": os_distribution,
                    "agent_token_hash": f"demo-token-hash-{hostname}",
                    "active": active,
                    "last_seen": last_seen,
                    "token_rotated_at": now - timedelta(days=1),
                },
            )
        Agent.objects.update_or_create(
            hostname=DISCOVERY_AGENT_HOSTNAME,
            agent_role=Agent.ROLE_DISCOVERY,
            defaults={
                "agent_url": f"https://{DISCOVERY_AGENT_HOSTNAME}:9443",
                "capabilities": ["agent.discovery"],
                "os_distribution": "Ubuntu 24.04",
                "agent_token_hash": f"demo-token-hash-{DISCOVERY_AGENT_HOSTNAME}",
                "active": True,
                "last_seen": now - timedelta(minutes=1),
                "token_rotated_at": now - timedelta(days=1),
            },
        )

    def _seed_scan_job(self, targets, now):
        total_scan_runs = self._scan_run_count(targets, SCAN_SCANNERS)
        async_job = AsyncJob.objects.create(
            kind="scan_job",
            status=AsyncJob.COMPLETED,
            request_payload={
                "scenario": SCENARIO,
                "target_ids": [target.id for target in targets.values()],
                "scanners": SCAN_SCANNERS,
            },
            progress={"completed": total_scan_runs, "total": total_scan_runs},
            started_at=now - timedelta(minutes=55),
            finished_at=now - timedelta(minutes=38),
            result={"snapshot_serial": f"{SERIAL_PREFIX}-latest", "findings_count": len(LATEST_ASSETS)},
        )
        scan_job = ScanJob.objects.create(
            async_job=async_job,
            target_ids=[target.id for target in targets.values()],
            scanner_selection=SCAN_SCANNERS,
        )
        async_job.resource_id = scan_job.id
        async_job.save(update_fields=["resource_id"])
        self._timestamp(async_job, created_at=now - timedelta(minutes=56), updated_at=now - timedelta(minutes=38))
        self._timestamp(scan_job, created_at=now - timedelta(minutes=56), updated_at=now - timedelta(minutes=38))
        self._seed_scan_logs(async_job, targets, now)
        return scan_job

    def _seed_scan_logs(self, async_job, targets, now):
        scanner_kinds = SCAN_SCANNERS
        target_list = list(targets.values())
        for index, target in enumerate(target_list):
            for scanner_index, scanner_kind in enumerate(scanner_kinds):
                if scanner_kind.startswith("agent.") and not target.agent_enabled:
                    continue
                started_at = now - timedelta(minutes=54) + timedelta(seconds=(index * 35) + scanner_index * 5)
                finished_at = started_at + timedelta(seconds=3)
                ScanRunLog.objects.create(
                    async_job=async_job,
                    target=target,
                    scanner_kind=scanner_kind,
                    status="COMPLETED",
                    findings_count=1 + ((index + scanner_index) % 3),
                    started_at=started_at,
                    finished_at=finished_at,
                )

    def _scan_run_count(self, targets, scanner_kinds):
        return sum(
            1
            for target in targets.values()
            for scanner_kind in scanner_kinds
            if not scanner_kind.startswith("agent.") or target.agent_enabled
        )

    def _seed_snapshot(self, label, assets, targets, scan_job, created_at):
        serial = f"{SERIAL_PREFIX}-{label}"
        snapshot = CbomSnapshot.objects.create(
            scan_job=scan_job,
            serial_number=serial,
            summary=self._snapshot_summary(assets),
            validation_errors=[],
        )
        self._timestamp(snapshot, created_at=created_at, updated_at=created_at + timedelta(minutes=2))
        created_assets = {}
        for asset_data in assets:
            asset = Asset.objects.create(
                snapshot=snapshot,
                target=targets[asset_data.target_key],
                name=asset_data.name,
                asset_class="crypto",
                asset_type=asset_data.asset_type,
                bom_ref=asset_data.bom_ref,
                algorithm=asset_data.algorithm,
                algorithm_family=asset_data.algorithm_family,
            )
            created_assets[asset_data.bom_ref] = asset
            RiskScore.objects.create(
                snapshot=snapshot,
                asset=asset,
                score=asset_data.score,
                tier=asset_data.tier,
                factors={**asset_data.factors, "weights": {"wA": 1.4, "wD": 1.2, "wE": 1.1, "wL": 1.3, "wC": 1.5}},
            )
            if asset_data.tier in {"CRITICAL", "HIGH"}:
                self._seed_qualitative(asset)
            if asset_data.bom_ref == "postgres:client:tls-policy":
                AssetContextOverride.objects.create(
                    asset=asset,
                    sensitivity="critical",
                    lifespan_years=6,
                    criticality="high",
                    exposure="internal_network",
                    service_role="PostgreSQL client TLS policy exception",
                    override_keys=["sensitivity", "lifespan_years", "criticality", "exposure", "service_role"],
                )
        self._seed_dependencies(snapshot, created_assets)
        return snapshot

    def _seed_performance_runs(self, baseline, latest, created_at):
        baseline_run = performance_services.create_run(
            baseline,
            {
                "trigger": "manual",
                "profile": "smoke",
                "environment": {"scenario": SCENARIO, "location": "testbed", "sample_count": 30},
            },
        )
        self._timestamp(baseline_run, created_at=created_at - timedelta(days=2), updated_at=created_at - timedelta(days=2))
        for asset in baseline.assets.select_related("target").all():
            performance_services.upsert_result(
                baseline_run,
                {
                    "asset_id": asset.id,
                    "compatibility_status": "PASS",
                    "negotiated_algorithm": asset.algorithm,
                    "metrics": self._performance_metrics(asset, migrated=False),
                },
            )
        performance_services.update_run_status(baseline_run, "COMPLETED")

        latest_run = performance_services.create_run(
            latest,
            {
                "baseline_snapshot_id": baseline.id,
                "trigger": "post_migration",
                "profile": "smoke",
                "environment": {"scenario": SCENARIO, "location": "testbed", "sample_count": 30},
            },
        )
        self._timestamp(latest_run, created_at=created_at, updated_at=created_at)
        for asset in latest.assets.select_related("target").all():
            performance_services.upsert_result(
                latest_run,
                {
                    "asset_id": asset.id,
                    "compatibility_status": "PASS",
                    "negotiated_algorithm": asset.algorithm,
                    "metrics": self._performance_metrics(asset, migrated=asset.algorithm_family in {"ML-DSA", "ML-KEM"}),
                },
            )
        performance_services.update_run_status(latest_run, "COMPLETED")

    def _performance_metrics(self, asset, *, migrated):
        host_weight = (asset.target.port if asset.target else 443) % 11
        base_handshake = 78 + host_weight
        base_ttfb = 142 + host_weight * 3
        if migrated:
            base_handshake += 24
            base_ttfb += 12
        elif asset.algorithm_family in {"RSA", "ECDSA", "DH"}:
            base_handshake += 8
        return {
            "tcp_connect_ms": {"p50": 8 + host_weight, "p95": 15 + host_weight, "samples": 30},
            "handshake_ms": {"p50": base_handshake * 0.62, "p95": base_handshake, "samples": 30},
            "ttfb_ms": {"p50": base_ttfb * 0.66, "p95": base_ttfb, "samples": 30},
            "total_request_ms": {"p50": (base_ttfb + 50) * 0.68, "p95": base_ttfb + 50, "samples": 30},
            "failure_rate": 0.0 if asset.algorithm_family != "UNKNOWN" else 0.015,
            "timeout_rate": 0.0,
            "session_resumption_rate": 0.72,
            "handshake_bytes_sent": 2100 + (1400 if migrated else 0),
            "handshake_bytes_received": 3900 + (2600 if migrated else 0),
        }

    def _seed_dependencies(self, snapshot, assets):
        for source_ref, target_ref, semantic in DEMO_DEPENDENCIES:
            if source_ref in assets and target_ref in assets:
                AssetDependency.objects.create(
                    snapshot=snapshot,
                    source_asset=assets[source_ref],
                    target_asset=assets[target_ref],
                    semantic=semantic,
                )

    def _seed_qualitative(self, asset):
        QualitativeAssessment.objects.create(
            asset=asset,
            provider="demo-rulebook",
            summary=f"{asset.name} uses {asset.algorithm}, which is exposed to quantum migration planning.",
            threat_scenarios=["store_now_decrypt_later", "long_lived_service_identity", "migration_dependency_delay"],
            migration_recommendation="Prioritize inventory owner confirmation, compatibility testing, and hybrid/PQC rollout planning.",
            confidence=0.78,
        )

    def _seed_discovery(self, targets, created_at):
        promoted_count = sum(1 for *_, promoted, target_key in DISCOVERY_ENDPOINTS if promoted and target_key)
        discovery_agent = Agent.objects.filter(hostname=DISCOVERY_AGENT_HOSTNAME, agent_role=Agent.ROLE_DISCOVERY).first()
        async_job = AsyncJob.objects.create(
            kind="discovery",
            status=AsyncJob.COMPLETED,
            request_payload={
                "scenario": SCENARIO,
                "scope_type": "cidr",
                "scope_value": "172.20.0.0/16",
                "executor_type": "agent",
                "agent_id": str(discovery_agent.id) if discovery_agent else None,
                "ports": DISCOVERY_PORTS,
            },
            progress={"completed": len(DISCOVERY_ENDPOINTS), "total": len(DISCOVERY_ENDPOINTS)},
            started_at=created_at,
            finished_at=created_at + timedelta(minutes=6),
            result={"endpoint_count": len(DISCOVERY_ENDPOINTS), "promoted_count": promoted_count},
        )
        discovery = Discovery.objects.create(
            async_job=async_job,
            scope_type="cidr",
            scope_value="172.20.0.0/16",
            cidr="172.20.0.0/16",
            executor_type="agent" if discovery_agent else "central",
            discovery_agent=discovery_agent,
            ports=DISCOVERY_PORTS,
            include_default_ports=True,
            status=AsyncJob.COMPLETED,
            started_at=async_job.started_at,
            finished_at=async_job.finished_at,
        )
        async_job.resource_id = discovery.id
        async_job.save(update_fields=["resource_id"])
        self._timestamp(async_job, created_at=created_at - timedelta(minutes=1), updated_at=created_at + timedelta(minutes=6))
        self._timestamp(discovery, created_at=created_at - timedelta(minutes=1), updated_at=created_at + timedelta(minutes=6))
        for host, port, transport, detected_protocol, suggested_protocol_hint, promoted, target_key in DISCOVERY_ENDPOINTS:
            DiscoveredEndpoint.objects.create(
                discovery=discovery,
                host=host,
                port=port,
                transport=transport,
                detected_protocol=detected_protocol,
                suggested_protocol_hint=suggested_protocol_hint,
                promoted=promoted,
                target=targets.get(target_key) if target_key else None,
            )
        return discovery

    def _seed_recompute_job(self, snapshot, created_at):
        async_job = AsyncJob.objects.create(
            kind="recompute",
            status=AsyncJob.COMPLETED,
            request_payload={
                "scenario": SCENARIO,
                "snapshot_id": snapshot.id,
                "weights": {"wA": 1.4, "wD": 1.2, "wE": 1.1, "wL": 1.3, "wC": 1.5},
                "persist_weights_as_default": True,
            },
            progress={"completed": snapshot.assets.count(), "total": snapshot.assets.count()},
            started_at=created_at,
            finished_at=created_at + timedelta(minutes=2),
            result={"updated_scores": snapshot.assets.count()},
        )
        async_job.resource_id = async_job.id
        async_job.save(update_fields=["resource_id"])
        self._timestamp(async_job, created_at=created_at - timedelta(minutes=1), updated_at=created_at + timedelta(minutes=2))

    def _seed_failed_scan_job(self, targets, created_at):
        db_target = targets[("db.testbed.local", 5432, "TCP")]
        target_count = len(targets)
        async_job = AsyncJob.objects.create(
            kind="scan_job",
            status=AsyncJob.FAILED,
            request_payload={
                "scenario": SCENARIO,
                "target_ids": [target.id for target in targets.values()],
                "scanners": ["network", "agent.keystore", "agent.pkg_keyring"],
            },
            progress={"completed": min(11, target_count), "total": target_count, "current_target": "db.testbed.local", "current_scanner": "agent.keystore"},
            started_at=created_at,
            finished_at=created_at + timedelta(minutes=1),
            error={"code": "agent_stale", "message": "db.testbed.local agent did not report within freshness window."},
        )
        scan_job = ScanJob.objects.create(
            async_job=async_job,
            target_ids=[target.id for target in targets.values()],
            scanner_selection=["network", "agent.keystore", "agent.pkg_keyring"],
        )
        async_job.resource_id = scan_job.id
        async_job.save(update_fields=["resource_id"])
        self._timestamp(async_job, created_at=created_at - timedelta(minutes=1), updated_at=created_at + timedelta(minutes=1))
        self._timestamp(scan_job, created_at=created_at - timedelta(minutes=1), updated_at=created_at + timedelta(minutes=1))
        ScanRunLog.objects.create(
            async_job=async_job,
            target=db_target,
            scanner_kind="agent.keystore",
            status="FAILED",
            findings_count=0,
            started_at=created_at + timedelta(seconds=20),
            finished_at=created_at + timedelta(seconds=48),
            error="agent_stale",
        )

    def _seed_cancelled_discovery(self, created_at):
        async_job = AsyncJob.objects.create(
            kind="discovery",
            status=AsyncJob.CANCELLED,
            request_payload={"scenario": SCENARIO, "cidr": "172.21.0.0/24", "ports": [22, 443]},
            progress={"completed": 2, "total": 24, "current_target": "172.21.0.14"},
            cancel_requested_at=created_at + timedelta(seconds=35),
            started_at=created_at,
            finished_at=created_at + timedelta(minutes=1),
            result={"endpoint_count": 0},
        )
        discovery = Discovery.objects.create(
            async_job=async_job,
            cidr="172.21.0.0/24",
            ports=[22, 443],
            include_default_ports=False,
            status=AsyncJob.CANCELLED,
            started_at=async_job.started_at,
            finished_at=async_job.finished_at,
            error="cancel_requested",
        )
        async_job.resource_id = discovery.id
        async_job.save(update_fields=["resource_id"])
        self._timestamp(async_job, created_at=created_at - timedelta(minutes=1), updated_at=created_at + timedelta(minutes=1))
        self._timestamp(discovery, created_at=created_at - timedelta(minutes=1), updated_at=created_at + timedelta(minutes=1))

    def _snapshot_summary(self, assets):
        by_tier = {}
        by_asset_type = {}
        by_algorithm_family = {}
        for asset in assets:
            by_tier[asset.tier] = by_tier.get(asset.tier, 0) + 1
            by_asset_type[asset.asset_type] = by_asset_type.get(asset.asset_type, 0) + 1
            by_algorithm_family[asset.algorithm_family] = by_algorithm_family.get(asset.algorithm_family, 0) + 1
        return {
            "scenario": SCENARIO,
            "asset_count": len(assets),
            "target_count": len({asset.target_key for asset in assets}),
            "by_tier": by_tier,
            "by_asset_type": by_asset_type,
            "by_algorithm_family": by_algorithm_family,
        }

    def _timestamp(self, instance, *, created_at=None, updated_at=None):
        updates = {}
        if created_at and hasattr(instance, "created_at"):
            updates["created_at"] = created_at
        if updated_at and hasattr(instance, "updated_at"):
            updates["updated_at"] = updated_at
        if updates:
            type(instance).objects.filter(pk=instance.pk).update(**updates)
