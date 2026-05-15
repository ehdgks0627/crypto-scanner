from migration_engine.engine import MAPPING_RULES_PATH, candidate_for_algorithm, mapping_config, recommend_migration


def test_migration_mapping_rules_are_loaded_from_external_config():
    config = mapping_config()

    assert MAPPING_RULES_PATH.name == "mapping_rules.json"
    assert MAPPING_RULES_PATH.exists()
    assert config["version"] == "migration-mapping-v1"
    assert {rule["id"] for rule in config["rules"]} >= {
        "rsa-signature",
        "rsa-kem-like",
        "ecdsa-p256-aliases",
        "ecdsa-default",
        "ecdh-x25519-p256-kex",
        "dh-kex-aliases",
        "dh-default",
    }
    assert candidate_for_algorithm("RSA-2048", "RSA", "certificate") == {
        "kind": "signature",
        "purpose": "digital_signature",
        "hybrid_set": ["RSA-2048", "ML-DSA-65"],
        "replace_set": ["ML-DSA-65"],
        "long_term_hybrid_set": ["RSA-2048", "SLH-DSA-SHA2-128s"],
        "long_term_replace_set": ["SLH-DSA-SHA2-128s"],
        "classically_weak": False,
    }


def test_migration_mapping_rules_classify_kem_and_signature_paths_separately():
    assert candidate_for_algorithm("RSA-2048", "RSA", "key")["kind"] == "kem"
    assert candidate_for_algorithm("RSA-2048", "RSA", "key")["purpose"] == "key_exchange"
    assert candidate_for_algorithm("RSA-2048", "RSA", "key_agreement")["replace_set"] == ["ML-KEM-768"]
    assert candidate_for_algorithm("RSA-2048", "RSA", "key_agreement")["purpose"] == "key_exchange"
    assert candidate_for_algorithm("ECDSA-P384", "ECDSA", "certificate")["replace_set"] == ["ML-DSA-87"]
    assert candidate_for_algorithm("ECDSA-P384", "ECDSA", "certificate")["purpose"] == "digital_signature"
    assert candidate_for_algorithm("ECDSA-P-256", "ECDSA", "certificate")["replace_set"] == ["ML-DSA-65"]
    assert candidate_for_algorithm("prime256v1", None, "certificate")["replace_set"] == ["ML-DSA-65"]
    assert candidate_for_algorithm("secp256r1", None, "ssh_host_key")["purpose"] == "digital_signature"
    assert candidate_for_algorithm("ECDH-P384", "ECDH", "protocol")["replace_set"] == ["ML-KEM-1024"]
    assert candidate_for_algorithm("ECDH-P384", "ECDH", "protocol")["purpose"] == "key_agreement"
    assert candidate_for_algorithm("X25519", None, "key_agreement")["replace_set"] == ["ML-KEM-768"]
    assert candidate_for_algorithm("curve25519-sha256", None, "protocol")["purpose"] == "key_agreement"
    assert candidate_for_algorithm("ECP-256", None, "key_agreement")["replace_set"] == ["ML-KEM-768"]
    assert candidate_for_algorithm("diffie-hellman-group14-sha256", None, "protocol")["replace_set"] == ["ML-KEM-768"]
    assert candidate_for_algorithm("MODP-2048", "DH", "key_agreement")["purpose"] == "key_agreement"
    assert candidate_for_algorithm("SHA-256", "SHA", "algorithm")["kind"] == "safe_classical"
    assert candidate_for_algorithm("SHA-256", "SHA", "algorithm")["purpose"] == "hash_integrity"


def test_migration_mapping_rules_infer_pqc_asset_purpose():
    assert candidate_for_algorithm("ML-KEM-768", "ML-KEM", "protocol")["purpose"] == "key_exchange"
    assert candidate_for_algorithm("ML-DSA-65", "ML-DSA", "certificate")["purpose"] == "digital_signature"
    assert candidate_for_algorithm("SLH-DSA-SHA2-128s", "SLH-DSA", "certificate")["purpose"] == "long_term_signature"


def test_migration_engine_recommends_hybrid_first_for_long_lived_rsa():
    item = recommend_migration(
        asset_id=7,
        asset_name="public web certificate",
        asset_type="certificate",
        algorithm="RSA-2048",
        algorithm_family="RSA",
        risk_score=95,
        tier="CRITICAL",
        context={
            "sensitivity": "critical",
            "lifespan_years": 25,
            "criticality": "critical",
            "exposure": "public_internet",
            "service_role": "pki",
        },
        capabilities=[],
    )

    assert item["recommendation"]["strategy"] == "hybrid"
    assert item["asset_purpose"] == "digital_signature"
    assert item["recommendation"]["phase"] == "hybrid_first"
    assert item["recommendation"]["target_algorithm_set"] == ["RSA-2048", "ML-DSA-65"]
    assert item["recommendation"]["final_algorithm_set"] == ["ML-DSA-65"]
    assert "runtime_capability_unknown" in item["recommendation"]["blockers"]
    assert "enable_hybrid" in [step["kind"] for step in item["playbook"]]
    assert item["agility"]["level"] == "LOW"


def test_migration_engine_maps_rsa_key_exchange_to_ml_kem_without_changing_signature_path():
    key_exchange_item = recommend_migration(
        asset_id=10,
        asset_name="legacy RSA key exchange",
        asset_type="key_agreement",
        algorithm="RSA-2048",
        algorithm_family="RSA",
        risk_score=81,
        tier="HIGH",
        context={"lifespan_years": 10, "criticality": "high", "exposure": "public_internet"},
        capabilities=["runtime_pqc_supported", "config_policy", "rescan_validation", "rollback_supported"],
    )
    certificate_item = recommend_migration(
        asset_id=11,
        asset_name="legacy RSA certificate",
        asset_type="certificate",
        algorithm="RSA-2048",
        algorithm_family="RSA",
        risk_score=81,
        tier="HIGH",
        context={"lifespan_years": 10, "criticality": "high", "exposure": "public_internet"},
        capabilities=["runtime_pqc_supported", "config_policy", "rescan_validation", "rollback_supported"],
    )

    assert key_exchange_item["asset_purpose"] == "key_exchange"
    assert key_exchange_item["recommendation"]["target_algorithm_set"] == ["X25519", "ML-KEM-768"]
    assert key_exchange_item["recommendation"]["final_algorithm_set"] == ["ML-KEM-768"]
    assert certificate_item["asset_purpose"] == "digital_signature"
    assert certificate_item["recommendation"]["target_algorithm_set"] == ["RSA-2048", "ML-DSA-65"]
    assert certificate_item["recommendation"]["final_algorithm_set"] == ["ML-DSA-65"]


def test_migration_engine_maps_ecdsa_p256_aliases_to_ml_dsa_65():
    item = recommend_migration(
        asset_id=12,
        asset_name="curve-only ECDSA certificate",
        asset_type="certificate",
        algorithm="prime256v1",
        algorithm_family=None,
        risk_score=79,
        tier="HIGH",
        context={"lifespan_years": 8, "criticality": "high", "exposure": "public_internet"},
        capabilities=["runtime_pqc_supported", "config_policy", "rescan_validation", "rollback_supported"],
    )

    assert item["asset_purpose"] == "digital_signature"
    assert item["current"]["quantum_vulnerable"] is True
    assert item["recommendation"]["target_algorithm_set"] == ["ECDSA P-256", "ML-DSA-65"]
    assert item["recommendation"]["final_algorithm_set"] == ["ML-DSA-65"]


def test_migration_engine_maps_x25519_and_dh_aliases_to_ml_kem_768():
    x25519_item = recommend_migration(
        asset_id=13,
        asset_name="ssh curve25519 kex",
        asset_type="protocol",
        algorithm="curve25519-sha256",
        algorithm_family=None,
        risk_score=82,
        tier="HIGH",
        context={"lifespan_years": 10, "criticality": "high", "exposure": "internal_network"},
        capabilities=["runtime_pqc_supported", "config_policy", "rescan_validation", "rollback_supported"],
    )
    dh_item = recommend_migration(
        asset_id=14,
        asset_name="ike modp group",
        asset_type="key_agreement",
        algorithm="diffie-hellman-group14-sha256",
        algorithm_family=None,
        risk_score=82,
        tier="HIGH",
        context={"lifespan_years": 10, "criticality": "high", "exposure": "internal_network"},
        capabilities=["runtime_pqc_supported", "config_policy", "rescan_validation", "rollback_supported"],
    )

    assert x25519_item["asset_purpose"] == "key_agreement"
    assert x25519_item["current"]["quantum_vulnerable"] is True
    assert x25519_item["recommendation"]["target_algorithm_set"] == ["X25519", "ML-KEM-768"]
    assert x25519_item["recommendation"]["final_algorithm_set"] == ["ML-KEM-768"]
    assert dh_item["asset_purpose"] == "key_agreement"
    assert dh_item["current"]["quantum_vulnerable"] is True
    assert dh_item["recommendation"]["target_algorithm_set"] == ["X25519", "ML-KEM-768"]
    assert dh_item["recommendation"]["final_algorithm_set"] == ["ML-KEM-768"]


def test_migration_engine_maps_long_term_signatures_to_slh_dsa():
    archive_item = recommend_migration(
        asset_id=15,
        asset_name="artifact archive signing certificate",
        asset_type="certificate",
        algorithm="ECDSA-P-256",
        algorithm_family="ECDSA",
        risk_score=86,
        tier="HIGH",
        context={"service_role": "archive-signing", "lifespan_years": 25, "criticality": "high"},
        capabilities=["runtime_pqc_supported", "config_policy", "rescan_validation", "rollback_supported"],
    )
    default_item = recommend_migration(
        asset_id=16,
        asset_name="regular web signing certificate",
        asset_type="certificate",
        algorithm="ECDSA-P-256",
        algorithm_family="ECDSA",
        risk_score=86,
        tier="HIGH",
        context={"service_role": "web-frontend", "lifespan_years": 25, "criticality": "high"},
        capabilities=["runtime_pqc_supported", "config_policy", "rescan_validation", "rollback_supported"],
    )

    assert archive_item["asset_purpose"] == "long_term_signature"
    assert archive_item["recommendation"]["target_algorithm_set"] == ["ECDSA P-256", "SLH-DSA-SHA2-128s"]
    assert archive_item["recommendation"]["final_algorithm_set"] == ["SLH-DSA-SHA2-128s"]
    assert "hash-based SLH-DSA" in archive_item["recommendation"]["rationale"]
    assert default_item["asset_purpose"] == "digital_signature"
    assert default_item["recommendation"]["target_algorithm_set"] == ["ECDSA P-256", "ML-DSA-65"]
    assert default_item["recommendation"]["final_algorithm_set"] == ["ML-DSA-65"]


def test_migration_engine_marks_pqc_assets_as_no_change_with_high_agility():
    item = recommend_migration(
        asset_id=8,
        asset_name="pqc certificate",
        asset_type="certificate",
        algorithm="ML-DSA-65",
        algorithm_family="ML-DSA",
        risk_score=0,
        tier="LOW",
        context={"service_role": "pki"},
        capabilities=["config_policy", "automated_rotation", "rollback_supported", "rescan_validation", "owner_known"],
    )

    assert item["current"]["quantum_vulnerable"] is False
    assert item["asset_purpose"] == "digital_signature"
    assert item["recommendation"]["strategy"] == "no_change"
    assert item["recommendation"]["phase"] == "monitor"
    assert item["recommendation"]["target_algorithm_set"] == ["ML-DSA-65"]
    assert item["recommendation"]["blockers"] == []
    assert item["playbook"][0]["kind"] == "monitor"
    assert item["agility"]["level"] == "HIGH"


def test_migration_engine_replaces_classically_weak_sha1_signing():
    item = recommend_migration(
        asset_id=9,
        asset_name="legacy signature",
        asset_type="algorithm",
        algorithm="SHA-1",
        algorithm_family="SHA",
        risk_score=88,
        tier="CRITICAL",
        context={"lifespan_years": 2, "criticality": "medium", "exposure": "internal_network"},
        capabilities=["config_policy"],
    )

    assert item["recommendation"]["strategy"] == "replace"
    assert item["asset_purpose"] == "digital_signature"
    assert item["recommendation"]["phase"] == "replace_now"
    assert item["recommendation"]["target_algorithm"] == "SHA-256+"
    assert item["recommendation"]["target_algorithm_set"] == ["SHA-256+"]
    assert item["alternatives"] == []
    assert "rollback_undefined" in item["agility"]["blockers"]
