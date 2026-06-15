def assert_error_envelope(response, expected_status, expected_code):
    assert response.status_code == expected_status
    body = response.json()
    assert body["status"] == expected_status
    assert body["error"]["code"] == expected_code
    assert "message" in body["error"]
    assert "request_id" in body["error"]


def test_missing_api_key_uses_standard_error_envelope(client):
    response = client.post("/shell", json={})
    assert_error_envelope(response, 403, "missing_api_key")
    assert "x-api-key" in response.json()["error"].get("hint", "")


def test_validation_error_uses_standard_error_envelope(client, auth_headers):
    response = client.post("/agent/coding-task", headers=auth_headers, json={})
    assert_error_envelope(response, 422, "validation_error")
    assert isinstance(response.json()["error"].get("details"), list)


def test_route_not_found_uses_standard_error_envelope(client):
    response = client.get("/definitely-not-a-real-route")
    assert_error_envelope(response, 404, "route_not_found")


def test_unsupported_api_namespace_uses_structured_error(client):
    response = client.get("/api/agents")
    assert_error_envelope(response, 404, "unsupported_namespace")
    assert response.json()["error"]["path"] == "/api/agents"
