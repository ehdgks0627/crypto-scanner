import pytest


pytestmark = pytest.mark.django_db


def test_demo_session_starts_with_deterministic_targets(client):
    response = client.get("/api/demo/session")

    assert response.status_code == 200
    body = response.json()
    assert body["scenario"] == "final_presentation_demo"
    assert body["current_step"] == 0
    assert body["current_step_id"] == "targets"
    assert len(body["targets"]) == 13
    assert body["host_labels"][0] == {
        "host": "srv-01",
        "description": "외부 결제 API",
        "role": "edge-proxy",
        "data_classes": ["PII", "payment"],
        "partners": ["PG-A"],
        "retention": "7y",
    }


def test_demo_session_advances_to_full_scenario(client):
    client.post("/api/demo/session/start")
    for _ in range(5):
        response = client.post("/api/demo/session/next")
        assert response.status_code == 200

    body = response.json()
    assert body["current_step_id"] == "verification"
    assert body["agent_run"]["total_assets"] == 47
    assert body["agent_run"]["discovery_assets"] == 28
    assert body["agent_run"]["host_assets"] == 24
    assert body["agent_run"]["overlap_assets"] == 5
    assert body["agent_run"]["active_keys"] == 44
    assert body["agent_run"]["dormant_keys"] == 3
    assert body["agent_run"]["algorithm_distribution"] == [
        {"label": "RSA", "count": 14, "quantum_vulnerable": True},
        {"label": "ECDSA", "count": 6, "quantum_vulnerable": True},
        {"label": "Ed25519", "count": 5, "quantum_vulnerable": True},
        {"label": "DH/X25519", "count": 8, "quantum_vulnerable": True},
        {"label": "AES/ChaCha20", "count": 9, "quantum_vulnerable": False},
        {"label": "SHA256/SHA512", "count": 5, "quantum_vulnerable": False},
    ]
    assert len(body["assets"]) == 47
    assert body["risk"]["summary"] == {"P1": 12, "P2": 8, "P3": 27}
    assert body["risk"]["example"]["asset_id"] == "srv-01:443/tls"
    assert body["risk"]["example"]["score"] == 9.2
    assert body["risk"]["example"]["priority"] == "P1"
    assert set(body["risk"]["example"]["criteria"]) == {
        "value",
        "data",
        "scope",
        "sharing",
        "critical",
        "lifetime",
    }
    for criterion in body["risk"]["example"]["criteria"].values():
        assert criterion["level"] in {"HIGH", "MED", "LOW"}
        assert isinstance(criterion["reason"], str)
        assert criterion["reason"]
    assert body["migration"]["recommendation_count"] == 20
    migration_items = body["migration"]["items"]
    assert {item["priority"] for item in migration_items} <= {"P1", "P2"}
    assert any(
        item["current_algorithm"] == "RSA-2048" and item["recommended_algorithm"] == "ML-KEM-768"
        for item in migration_items
    )
    assert any(
        item["current_algorithm"] == "RSA-2048" and item["recommended_algorithm"] == "ML-DSA-65"
        for item in migration_items
    )
    assert any(
        item["current_algorithm"] == "ECDSA-P256" and item["recommended_algorithm"] == "ML-DSA-65"
        for item in migration_items
    )
    assert any(
        item["current_algorithm"] == "X25519" and item["recommended_algorithm"] == "ML-KEM-768"
        for item in migration_items
    )
    assert body["verification"]["handshake_success_rate"] == 100
    assert body["verification"]["latency_before_ms"] == 42
    assert body["verification"]["latency_after_ms"] == 54
    assert body["verification"]["throughput_before_rps"] == 2400
    assert body["verification"]["throughput_after_rps"] == 2380
    assert body["verification"]["compatibility_before"] == 100
    assert body["verification"]["compatibility_after"] == 98
    assert body["verification"]["failure_count"] == 0
    assert body["verification"]["cbom_changes"] == 12
    assert body["verification"]["overall_status"] == "PASS"
    assert body["verification"]["checks"] == [
        {"name": "기능", "status": "PASS", "value": "TLS handshake 100%"},
        {"name": "응답 지연", "status": "PASS", "value": "p95 42ms -> 54ms"},
        {"name": "호환", "status": "PASS", "value": "100% -> 98%"},
        {"name": "회귀", "status": "PASS", "value": "실패 경로 0건"},
    ]


def test_demo_events_follow_current_step(client):
    client.post("/api/demo/session/start")
    for _ in range(5):
        client.post("/api/demo/session/next")

    response = client.get("/api/demo/session/events")

    assert response.status_code == 200
    body = response.json()
    messages = [item["message"] for item in body["items"]]
    assert "대상 13개와 srv-01 라벨 준비 완료" in messages
    assert "TLS 인증서 체인 9개 수집 완료" in messages
    assert "Discovery Agent 자산 28개 정리 완료" in messages
    assert "Host Agent 자산 24개 정리 완료" in messages
    assert "Enriched CBOM 47행 생성 완료" in messages
    assert "DHS 6기준 평가 47/47 완료" in messages
    assert "PQC 매핑 추천 20개 생성 완료" in messages
    assert "가용성 검증 PASS, 실패 경로 0건" in messages
