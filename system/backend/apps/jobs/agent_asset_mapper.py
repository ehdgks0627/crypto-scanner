from apps.jobs.scan_assets import AssetCandidate, family_from_algorithm, stable_bom_ref


TYPE_SCANNER_KIND = {
    "certificate_file": "agent.app_cert_files",
    "private_key_file": "agent.private_key_files",
    "dormant_private_key": "agent.private_key_files",
    "system_ca": "agent.cert_store",
    "postgres_tls_config": "agent.app_config",
    "keystore": "agent.keystore",
    "java_keystore": "agent.keystore",
    "ssh_authorized_key": "agent.ssh_userkey",
    "ssh_config": "agent.ssh_config",
    "jwt_signing_key": "agent.app_config",
    "mtls_trust_bundle": "agent.cert_store",
    "oidc_jwks": "agent.app_config",
    "saml_signing_certificate": "agent.app_cert_files",
    "saml_encryption_certificate": "agent.app_cert_files",
    "container_image_signing_key": "agent.pkg_keyring",
    "package_signing_key": "agent.pkg_keyring",
    "kms_key_reference": "agent.keystore",
    "backup_encryption_key": "agent.keystore",
    "tls_config": "agent.app_config",
}

TYPE_ASSET_TYPE = {
    "certificate_file": "certificate",
    "private_key_file": "key",
    "dormant_private_key": "key",
    "system_ca": "certificate",
    "postgres_tls_config": "protocol",
    "keystore": "keystore",
    "java_keystore": "keystore",
    "ssh_authorized_key": "ssh_user_key",
    "ssh_config": "protocol",
    "jwt_signing_key": "key",
    "mtls_trust_bundle": "certificate",
    "oidc_jwks": "key",
    "saml_signing_certificate": "certificate",
    "saml_encryption_certificate": "certificate",
    "container_image_signing_key": "key",
    "package_signing_key": "key",
    "kms_key_reference": "key",
    "backup_encryption_key": "key",
    "tls_config": "protocol",
}


def map_agent_findings(target, findings: list[dict], selected_scanners: set[str]) -> list[AssetCandidate]:
    candidates = []
    for finding in findings:
        source_scanner = TYPE_SCANNER_KIND.get(str(finding.get("type") or ""))
        if not source_scanner or source_scanner not in selected_scanners:
            continue
        for algorithm in _algorithms_for_finding(finding):
            candidates.append(_candidate_for_finding(target, finding, source_scanner, algorithm))
    return candidates


def _candidate_for_finding(target, finding: dict, source_scanner: str, algorithm: str) -> AssetCandidate:
    finding_type = str(finding.get("type") or "agent_finding")
    path = str(finding.get("path") or finding_type)
    asset_type = TYPE_ASSET_TYPE.get(finding_type, "crypto")
    return AssetCandidate(
        target_id=target.id,
        scanner_kind=source_scanner,
        name=f"{target.host} {finding_type} {path}",
        asset_type=asset_type,
        algorithm=algorithm,
        algorithm_family=family_from_algorithm(algorithm),
        bom_ref=f"{source_scanner}:{stable_bom_ref(target.host, finding_type, path, algorithm)}",
        metadata=_metadata_for_finding(finding, source_scanner, path),
    )


def _algorithms_for_finding(finding: dict) -> list[str]:
    algorithms = finding.get("algorithms")
    if isinstance(algorithms, list) and algorithms:
        return [str(item) for item in algorithms]
    kex_algorithms = finding.get("kex_algorithms")
    if isinstance(kex_algorithms, list) and kex_algorithms:
        return [str(item) for item in kex_algorithms]
    algorithm = finding.get("algorithm")
    if algorithm:
        return [str(algorithm)]
    minimum_tls_version = finding.get("minimum_tls_version")
    if minimum_tls_version:
        return [str(minimum_tls_version)]
    return ["unknown"]


def _metadata_for_finding(finding: dict, source_scanner: str, path: str) -> dict:
    metadata = {
        "scanner": source_scanner,
        "type": str(finding.get("type") or "agent_finding"),
        "path": path,
    }
    for key in [
        "fingerprint_sha256",
        "key_size_bits",
        "in_use",
        "dormant",
        "referenced_by",
        "source_scanners",
        "source_paths",
        "source_bom_refs",
        "format",
        "minimum_tls_version",
    ]:
        if key in finding and finding[key] is not None:
            metadata[key] = finding[key]
    return metadata
