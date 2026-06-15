def test_api_smoke_with_inprocess_client(client):
    routes_response = client.get("/debug/routes")
    assert routes_response.status_code == 200
    routes = routes_response.json()
    assert "/system/" in routes
    assert "/shell" in routes or "/shell/" in routes

    docs_response = client.get("/docs")
    assert docs_response.status_code == 200

    openapi_response = client.get("/openapi.json")
    assert openapi_response.status_code == 200
    assert openapi_response.json().get("paths")

    protected_response = client.get("/system/")
    assert protected_response.status_code == 403
    assert protected_response.json()["error"]["code"] in {"missing_api_key", "forbidden"}
