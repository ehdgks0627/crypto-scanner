import pytest

from risk_engine.prompts import (
    QUALITATIVE_RISK_PROMPT_VERSION,
    QualitativeRiskResponseParseError,
    build_qualitative_risk_prompt,
    parse_qualitative_risk_response,
)


def test_qualitative_risk_prompt_injects_asset_metadata_context_and_schema():
    prompt = build_qualitative_risk_prompt(
        asset={
            "id": 10,
            "name": "customer API certificate",
            "asset_type": "certificate",
            "algorithm": "RSA-2048",
            "algorithm_family": "RSA",
            "target_label": "api.testbed.local:443",
            "metadata": {"path": "/etc/nginx/server.crt", "fingerprint_sha256": "a" * 64},
        },
        context={
            "sensitivity": "critical",
            "lifespan_years": 15,
            "criticality": "critical",
            "exposure": "public_internet",
            "service_role": "customer-api",
        },
        context_sources={"sensitivity": "target", "lifespan_years": "target"},
        operational_context={
            "connected_service": {"label": "api.testbed.local:443", "protocol_hint": "TLS"},
            "file_paths": ["/etc/nginx/server.crt"],
            "data_classification": {"level": "critical", "source": "target"},
        },
        risk={"score": 95, "tier": "CRITICAL", "source": "risk_score"},
    )

    assert prompt["version"] == QUALITATIVE_RISK_PROMPT_VERSION
    assert "PQC migration risk analyst" in prompt["system"]
    assert prompt["version"] == "qualitative-risk-v2"
    assert "RSA-2048" in prompt["user"]
    assert "/etc/nginx/server.crt" in prompt["user"]
    assert "public_internet" in prompt["user"]
    assert "DHS Q1 asset_value" in prompt["user"]
    assert "operational_context" in prompt["user"]
    assert "Required JSON schema" in prompt["user"]
    assert "dhs_criteria" in prompt["user"]
    assert prompt["payload"]["asset"]["metadata"]["fingerprint_sha256"] == "a" * 64
    assert prompt["payload"]["context"]["lifespan_years"] == 15
    assert prompt["payload"]["operational_context"]["connected_service"]["protocol_hint"] == "TLS"
    assert prompt["payload"]["operational_context"]["data_classification"]["level"] == "critical"
    assert prompt["payload"]["risk"]["tier"] == "CRITICAL"


def test_parse_qualitative_risk_response_extracts_json_from_free_text():
    parsed = parse_qualitative_risk_response(
        """
        The assessment follows.
        ```json
        {
          "summary": "RSA asset protects public customer traffic.",
          "threat_scenarios": ["harvest_now_decrypt_later", "service_identity_compromise"],
          "migration_recommendation": "Use a hybrid certificate during transition.",
          "dhs_criteria": {
            "asset_value": {
              "question": "Q1: asset value based on external exposure and business importance.",
              "rating": "HIGH",
              "score": 86,
              "rationale": "The service is public and protects customer traffic.",
              "signals": ["public_internet", "customer-api"]
            }
          },
          "confidence": 86
        }
        ```
        """
    )

    assert parsed == {
        "summary": "RSA asset protects public customer traffic.",
        "threat_scenarios": ["harvest_now_decrypt_later", "service_identity_compromise"],
        "migration_recommendation": "Use a hybrid certificate during transition.",
        "dhs_criteria": {
            "asset_value": {
                "question": "Q1: asset value based on external exposure and business importance.",
                "rating": "high",
                "score": 0.86,
                "rationale": "The service is public and protects customer traffic.",
                "signals": ["public_internet", "customer-api"],
            }
        },
        "confidence": 0.86,
    }


def test_parse_qualitative_risk_response_rejects_missing_json():
    with pytest.raises(QualitativeRiskResponseParseError):
        parse_qualitative_risk_response("summary only without JSON")
