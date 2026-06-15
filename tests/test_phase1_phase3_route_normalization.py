import yaml
from pathlib import Path


SCHEMA_FILES = [
    "openapi.yaml",
    "coding-openapi.yaml",
    "coding-gpt-core-openapi.yaml",
    "cos-openapi.yaml",
]


def test_openapi_server_urls_have_no_trailing_slash():
    repo_root = Path(__file__).resolve().parents[1]
    for schema_file in SCHEMA_FILES:
        schema_path = repo_root / schema_file
        assert schema_path.exists(), schema_file
        data = yaml.safe_load(schema_path.read_text())
        for server in data.get("servers", []):
            url = server.get("url", "")
            assert not url.endswith("/"), f"{schema_file} server URL has trailing slash: {url}"


def test_core_post_routes_do_not_redirect(client, auth_headers):
    payloads = {
        "/shell": {"command": "echo ok", "timeout_seconds": 5},
        "/files": {"action": "exists", "path": "/tmp"},
        "/git": {"action": "status", "path": "/root/GPT-API"},
        "/monitor": {"type": "memory"},
        "/package": {"manager": "pip", "action": "list"},
        "/batch": {"operations": [{"action": "shell"}]},
        "/code": {"action": "run", "content": "print('ok')", "language": "python"},
        "/refactor": {"mode": "literal", "files": [], "dry_run": True},
    }
    for path, payload in payloads.items():
        response = client.post(path, headers=auth_headers, json=payload, follow_redirects=False)
        assert response.status_code != 307, f"{path} unexpectedly redirected"


def test_core_read_aliases_do_not_redirect(client, auth_headers):
    response = client.get("/system", headers=auth_headers, follow_redirects=False)
    assert response.status_code != 307

    response = client.post("/system", headers=auth_headers, json={}, follow_redirects=False)
    assert response.status_code != 307

    response = client.post("/apps/capabilities", headers=auth_headers, json={}, follow_redirects=False)
    assert response.status_code != 307


def test_duplicate_slashes_are_normalized_before_routing(client, auth_headers):
    response = client.post("http://testserver//agent/coding-task", headers=auth_headers, json={}, follow_redirects=False)
    assert response.status_code == 422

    response = client.post("http://testserver//repo/instructions", headers=auth_headers, json={}, follow_redirects=False)
    assert response.status_code == 422
