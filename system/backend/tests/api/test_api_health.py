import datetime as dt

import pytest


pytestmark = pytest.mark.django_db


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


def test_api_health_002_degrades_when_noncritical_dependency_is_down(client, monkeypatch):
    from apps.health import services

    monkeypatch.setattr(
        services,
        "get_component_statuses",
        lambda: {"api": "ok", "database": "ok", "redis": "down", "worker": "ok"},
    )

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    body = response.json()
    assert body["status"] == "degraded"
    assert body["redis"] == "down"
    assert body["api"] == "ok"
    assert body["database"] == "ok"
