import yaml
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_health_routes_are_available_without_auth(client):
    for path in ["/health", "/healthz", "/api/health"]:
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.json()["status"] == "ok"


def test_duplicate_slash_paths_are_normalized(client, auth_headers):
    response = client.post("/agent//coding-task", headers=auth_headers, json={})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_no_redirect_for_core_action_routes(client):
    for path in ["/shell", "/files", "/git", "/monitor", "/dispatch", "/package"]:
        response = client.post(path, json={}, follow_redirects=False)
        assert response.status_code != 307, path


def test_openapi_server_urls_do_not_end_with_slash():
    for rel in ["openapi.yaml", "cos-openapi.yaml", "coding-openapi.yaml", "coding-gpt-core-openapi.yaml"]:
        data = yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))
        for server in data.get("servers", []):
            assert not server["url"].endswith("/"), rel


def test_documented_typed_coding_endpoints_are_not_missing(client, auth_headers):
    for path in ["/repo/overview", "/repo/instructions", "/agent/coding-task", "/coding/repo/action"]:
        response = client.post(path, headers=auth_headers, json={})
        assert response.status_code != 404, path
        assert response.status_code in {200, 400, 422}, path
