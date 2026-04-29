import uuid

import pytest


pytestmark = pytest.mark.django_db


EMPTY_PAGE = {
    "items": [],
    "total": 0,
    "offset": 0,
    "limit": 20,
}


def test_api_com_001_request_id_is_returned_on_success(client):
    request_id = "11111111-1111-4111-8111-111111111111"

    response = client.get("/api/targets", headers={"X-Request-Id": request_id})

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == request_id
    assert response.json() == EMPTY_PAGE


def test_api_com_002_server_generates_request_id(client):
    response = client.get("/api/meta/protocols")

    assert response.status_code == 200
    uuid.UUID(response.headers["X-Request-Id"])


def test_api_com_003_validation_error_uses_standard_error_response(client):
    response = client.post(
        "/api/jobs",
        data={"target_ids": [], "scanners": []},
        content_type="application/json",
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "unprocessable"
    assert body["message"]
    assert isinstance(body["details"], dict)
    assert "detail" not in body


def test_api_com_004_not_found_uses_standard_error_response(client):
    response = client.get("/api/assets/999999")

    assert response.status_code == 404
    assert response.headers["X-Request-Id"]
    assert response.json() == {
        "error": "not_found",
        "message": "Resource not found.",
        "details": {},
    }


def test_api_com_005_csv_query_array_is_accepted(client):
    response = client.get("/api/snapshots/1/risks?tier=CRITICAL,HIGH")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "total", "offset", "limit"}
    assert body["items"]
    assert all(item["tier"] in {"CRITICAL", "HIGH"} for item in body["items"])


def test_api_com_006_repeated_query_array_is_rejected(client):
    response = client.get("/api/snapshots/1/risks?tier=CRITICAL&tier=HIGH")

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "validation_error"
    assert body["message"]
    assert body["details"]["parameter"] == "tier"
    assert body["details"]["expected"] == "CSV"


def test_api_com_007_internal_exception_uses_standard_error_response(client, monkeypatch):
    from apps.meta import services

    def raise_unexpected_error():
        raise RuntimeError("service failed")

    monkeypatch.setattr(services, "list_protocols", raise_unexpected_error)

    response = client.get("/api/meta/protocols")

    assert response.status_code == 500
    assert response.headers["X-Request-Id"]
    assert response.json() == {
        "error": "internal",
        "message": "Internal server error.",
        "details": {},
    }


def test_api_lst_001_empty_list_endpoints_return_page_envelopes(client):
    for path in ("/api/targets", "/api/discoveries", "/api/jobs", "/api/snapshots", "/api/agents"):
        response = client.get(path)

        assert response.status_code == 200, path
        assert response.json() == EMPTY_PAGE
