import yaml

from main import app


CORE_POST_ENDPOINTS = [
    "/shell",
    "/files",
    "/git",
    "/monitor",
    "/package",
    "/batch",
]

TYPED_CODING_ENDPOINTS = [
    "/repo/overview",
    "/repo/instructions",
    "/repo/read-context",
    "/env/discover",
    "/env/doctor",
    "/env/prepare-dry-run",
    "/env/prepare-approved",
    "/quality/run",
    "/agent/coding-task",
    "/agent/coding-task/submit",
    "/agent/coding-task/next",
    "/agent/coding-task/finalize",
    "/agent/coding-task/smoke-test",
    "/coding/repo/action",
    "/coding/env/action",
    "/coding/quality/action",
]


def _route_methods():
    methods_by_path = {}
    for route in app.routes:
        methods = getattr(route, "methods", None)
        if not methods:
            continue
        methods_by_path.setdefault(route.path, set()).update(methods)
    return methods_by_path


def test_main_health_routes_are_available_without_auth(client):
    for path in ["/health", "/healthz", "/api/health"]:
        response = client.get(path)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["service"] == "gpt-api"
        assert "timestamp" in body


def test_unsupported_api_namespace_returns_structured_error(client):
    response = client.get("/api/agents")
    assert response.status_code == 404
    body = response.json()
    assert body["status"] == 404
    assert body["error"]["code"] == "unsupported_namespace"
    assert body["error"]["path"] == "/api/agents"


def test_core_post_endpoints_do_not_redirect_without_trailing_slash(client):
    for path in CORE_POST_ENDPOINTS:
        response = client.post(path, json={}, follow_redirects=False)
        assert response.status_code != 307, path
        assert response.status_code in {200, 400, 403, 422}, path


def test_get_read_endpoints_have_post_aliases(auth_headers, client):
    expectations = {
        "/system": {200},
        "/system/": {200},
        "/apps/capabilities": {200},
        "/apps/capabilities/": {200, 404},
    }
    # /apps/capabilities/ is allowed to be absent because the canonical route is
    # slashless under the apps router, but it must not redirect or method-fail.
    for path, allowed in expectations.items():
        response = client.post(path, headers=auth_headers, json={}, follow_redirects=False)
        assert response.status_code != 307, path
        assert response.status_code != 405, path
        assert response.status_code in allowed, path


def test_duplicate_slashes_are_normalized_before_routing(client):
    response = client.post("http://testserver//agent/coding-task", json={}, follow_redirects=False)
    assert response.status_code != 404
    assert response.status_code in {403, 422}


def test_typed_coding_routes_are_registered():
    methods_by_path = _route_methods()
    missing = [path for path in TYPED_CODING_ENDPOINTS if "POST" not in methods_by_path.get(path, set())]
    assert missing == []


def test_coding_schema_server_urls_have_no_trailing_slash():
    for path in ["openapi.yaml", "coding-openapi.yaml", "coding-gpt-core-openapi.yaml", "cos-openapi.yaml"]:
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        for server in data.get("servers", []):
            assert not server["url"].endswith("/"), path


def test_documented_coding_schema_paths_exist_in_app():
    methods_by_path = _route_methods()
    for schema_file in ["coding-openapi.yaml", "coding-gpt-core-openapi.yaml"]:
        with open(schema_file, encoding="utf-8") as handle:
            schema = yaml.safe_load(handle)
        missing = []
        for path, methods in schema.get("paths", {}).items():
            if path.startswith("/openapi"):
                continue
            live_methods = methods_by_path.get(path, set())
            for method in methods:
                if method.upper() not in live_methods:
                    missing.append(f"{method.upper()} {path}")
        assert missing == [], f"{schema_file}: {missing[:20]}"
