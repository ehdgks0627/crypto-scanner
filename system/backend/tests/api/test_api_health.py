import datetime as dt


def test_api_health_001_returns_dependency_status(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"

    body = response.json()
    assert set(body) == {"status", "api", "database", "redis", "worker", "checked_at"}
    assert body["status"] == "ok"
    for key in ("api", "database", "redis", "worker"):
        assert body[key] in {"ok", "degraded", "down"}
    dt.datetime.fromisoformat(body["checked_at"].replace("Z", "+00:00"))
