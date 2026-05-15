from risk_engine.prompts import QUALITATIVE_RISK_PROMPT_VERSION, build_qualitative_risk_prompt


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
    assert "RSA-2048" in prompt["user"]
    assert "/etc/nginx/server.crt" in prompt["user"]
    assert "public_internet" in prompt["user"]
    assert "operational_context" in prompt["user"]
    assert "Required JSON schema" in prompt["user"]
    assert prompt["payload"]["asset"]["metadata"]["fingerprint_sha256"] == "a" * 64
    assert prompt["payload"]["context"]["lifespan_years"] == 15
    assert prompt["payload"]["operational_context"]["connected_service"]["protocol_hint"] == "TLS"
    assert prompt["payload"]["operational_context"]["data_classification"]["level"] == "critical"
    assert prompt["payload"]["risk"]["tier"] == "CRITICAL"
