from risk_engine.engine import DEFAULT_WEIGHTS, compute_risk, tier_for_score


def test_risk_engine_scores_quantum_vulnerable_public_critical_asset():
    result = compute_risk(
        algorithm="RSA-2048",
        algorithm_family="RSA",
        asset_type="certificate",
        context={
            "sensitivity": "critical",
            "lifespan_years": 25,
            "criticality": "critical",
            "exposure": "public_internet",
            "service_role": "pki",
        },
        weights=DEFAULT_WEIGHTS,
    )

    assert result.score == 95
    assert result.tier == "CRITICAL"
    assert result.factors == {"a": 0.95, "d": 1.0, "e": 1.0, "l": 1.0, "c": 1.0}


def test_risk_engine_keeps_pqc_assets_low_even_with_severe_context():
    result = compute_risk(
        algorithm="ML-DSA-65",
        algorithm_family="ML-DSA",
        asset_type="certificate",
        context={
            "sensitivity": "critical",
            "lifespan_years": 25,
            "criticality": "critical",
            "exposure": "public_internet",
            "service_role": "pki",
        },
        weights=DEFAULT_WEIGHTS,
    )

    assert result.score == 0
    assert result.tier == "LOW"
    assert result.factors["a"] == 0.0


def test_risk_engine_uses_heuristics_for_missing_context_and_target_ip():
    result = compute_risk(
        algorithm="ECDSA P-256",
        algorithm_family="ECDSA",
        asset_type="certificate",
        context={"service_role": "api-gateway"},
        weights=DEFAULT_WEIGHTS,
        target_ip="8.8.8.8",
        protocol_hint="TLS",
    )

    assert result.factors["a"] == 0.95
    assert result.factors["d"] == 0.5
    assert result.factors["e"] == 1.0
    assert result.factors["l"] == 0.5
    assert result.factors["c"] == 0.7
    assert result.sources["d"] == "heuristic"
    assert result.sources["e"] == "heuristic"


def test_risk_engine_applies_exponent_weights_and_tier_boundaries():
    base = compute_risk(
        algorithm="RSA-2048",
        algorithm_family="RSA",
        asset_type="key",
        context={
            "sensitivity": "high",
            "lifespan_years": 10,
            "criticality": "high",
            "exposure": "internal_network",
            "service_role": "web-frontend",
        },
        weights=DEFAULT_WEIGHTS,
    )
    dampened_algorithm = compute_risk(
        algorithm="RSA-2048",
        algorithm_family="RSA",
        asset_type="key",
        context={
            "sensitivity": "high",
            "lifespan_years": 10,
            "criticality": "high",
            "exposure": "internal_network",
            "service_role": "web-frontend",
        },
        weights={**DEFAULT_WEIGHTS, "wA": 0.5},
    )

    assert dampened_algorithm.weighted_raw > base.weighted_raw
    assert tier_for_score(80) == "CRITICAL"
    assert tier_for_score(60) == "HIGH"
    assert tier_for_score(30) == "MEDIUM"
    assert tier_for_score(29) == "LOW"
