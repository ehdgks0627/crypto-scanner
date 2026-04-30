from migration_engine.engine import recommend_migration


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
    assert item["recommendation"]["phase"] == "hybrid_first"
    assert item["recommendation"]["target_algorithm_set"] == ["RSA-2048", "ML-DSA-65"]
    assert item["recommendation"]["final_algorithm_set"] == ["ML-DSA-65"]
    assert "runtime_capability_unknown" in item["recommendation"]["blockers"]
    assert "enable_hybrid" in [step["kind"] for step in item["playbook"]]
    assert item["agility"]["level"] == "LOW"


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
    assert item["recommendation"]["phase"] == "replace_now"
    assert item["recommendation"]["target_algorithm"] == "SHA-256+"
    assert item["recommendation"]["target_algorithm_set"] == ["SHA-256+"]
    assert item["alternatives"] == []
    assert "rollback_undefined" in item["agility"]["blockers"]
