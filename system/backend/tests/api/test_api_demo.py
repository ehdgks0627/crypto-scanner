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
    assert len(body["assets"]) == 47
    assert body["risk"]["summary"] == {"P1": 12, "P2": 8, "P3": 27}
    assert body["risk"]["example"]["asset_id"] == "srv-01:443/tls"
    assert body["risk"]["example"]["score"] == 9.2
    assert body["risk"]["example"]["priority"] == "P1"
    assert body["migration"]["recommendation_count"] == 20
    assert body["verification"]["handshake_success_rate"] == 100
    assert body["verification"]["latency_before_ms"] == 42
    assert body["verification"]["latency_after_ms"] == 54
    assert body["verification"]["throughput_before_rps"] == 2400
    assert body["verification"]["throughput_after_rps"] == 2380
    assert body["verification"]["compatibility_before"] == 100
    assert body["verification"]["compatibility_after"] == 98
    assert body["verification"]["failure_count"] == 0
    assert body["verification"]["cbom_changes"] == 12


def test_demo_events_follow_current_step(client):
    client.post("/api/demo/session/start")
    client.post("/api/demo/session/next")

    response = client.get("/api/demo/session/events")

    assert response.status_code == 200
    body = response.json()
    messages = [item["message"] for item in body["items"]]
    assert "대상 13개와 srv-01 라벨 준비 완료" in messages
    assert "Discovery Agent 자산 28개 정리 완료" in messages
    assert "Host Agent 자산 24개 정리 완료" in messages
