import uuid


def test_api_com_001_request_id_is_returned_on_success(client):
    request_id = "11111111-1111-4111-8111-111111111111"

    response = client.get("/api/targets", headers={"X-Request-Id": request_id})

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == request_id
    assert response.json() == {
        "items": [],
        "total": 0,
        "offset": 0,
        "limit": 20,
    }


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
