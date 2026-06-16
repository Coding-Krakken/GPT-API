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



def test_phase7_telemetry_context_stamps_nested_events(tmp_path, monkeypatch):
    from utils import eval_telemetry
    from evals import report as eval_report

    events = tmp_path / "events.jsonl"
    monkeypatch.setenv("EVAL_TELEMETRY_EVENTS", str(events))
    monkeypatch.setenv("EVAL_TELEMETRY_ROOT", str(tmp_path))

    eval_telemetry.log_event("outside_event", repo_path="/tmp/outside")
    with eval_telemetry.telemetry_context(run_id="phase7_run", suite="phase7_backend_engines", case_id="backend_engine_metrics", repo_path="/tmp/repo"):
        eval_telemetry.log_event("repo_overview_completed", languages=["python"])
        with eval_telemetry.telemetry_context(runner="backend_engine_metrics"):
            eval_telemetry.log_event("workspace_created", workspace_path="/tmp/workspace")
        eval_telemetry.log_event("explicit_override", run_id="override_run")

    scoped = eval_report.load_events(run_id="phase7_run")
    assert {e["event_type"] for e in scoped} == {"repo_overview_completed", "workspace_created"}
    assert all(e["suite"] == "phase7_backend_engines" for e in scoped)
    assert all(e["case_id"] == "backend_engine_metrics" for e in scoped)
    assert any(e.get("runner") == "backend_engine_metrics" for e in scoped)
    assert eval_report.load_events(run_id="override_run")[0]["event_type"] == "explicit_override"


def test_phase7_report_engine_metrics_are_run_scoped(tmp_path, monkeypatch):
    from utils import eval_telemetry
    from evals import report as eval_report

    events = tmp_path / "events.jsonl"
    monkeypatch.setenv("EVAL_TELEMETRY_EVENTS", str(events))
    monkeypatch.setenv("EVAL_TELEMETRY_ROOT", str(tmp_path))

    eval_telemetry.log_event("repo_overview_completed", run_id="other_run", languages=["go"])
    with eval_telemetry.telemetry_context(run_id="phase7_run", suite="phase7_backend_engines", repo_path="/tmp/repo"):
        eval_telemetry.log_event("repo_overview_completed", languages=["python"], frameworks=["pytest"])
        eval_telemetry.log_event("workspace_created", workspace_path="/tmp/ws")
        eval_telemetry.log_event("tests_discovered", command_count=1, focused_count=1)
        eval_telemetry.log_event("quality_run", passed=True)
        eval_telemetry.log_event("policy_evaluated", action="commit", allowed=True, risk="low")

    report = eval_report.build_report(eval_report.load_events(run_id="phase7_run"), report_id="phase7_unit")
    assert report["summary"]["event_count"] == 5
    assert report["scores"]["engines"]["overall"] >= 80
    assert report["engine_metrics"]["repo_intelligence"]["languages_detected"] == ["python"]
    assert report["engine_metrics"]["workspace"]["created_count"] == 1
    assert report["engine_metrics"]["test_quality_engine"]["quality_run_count"] == 1
    assert report["engine_metrics"]["policy_engine"]["policy_event_count"] == 1


def test_phase7_eval_suite_result_exposes_engine_scores(tmp_path, monkeypatch):
    from utils import eval_telemetry
    from evals import run_eval_suite

    events = tmp_path / "events.jsonl"
    monkeypatch.setenv("EVAL_TELEMETRY_EVENTS", str(events))
    monkeypatch.setenv("EVAL_TELEMETRY_ROOT", str(tmp_path))

    def fake_run_suite(suite, repo_path, run_id=None):
        with eval_telemetry.telemetry_context(run_id=run_id, suite=suite, repo_path=repo_path, case_id="fake_phase7"):
            eval_telemetry.log_event("repo_overview_completed", languages=["python"])
            eval_telemetry.log_event("workspace_created", workspace_path="/tmp/ws")
            eval_telemetry.log_event("tests_discovered", command_count=1)
            eval_telemetry.log_event("quality_run", passed=True)
            eval_telemetry.log_event("policy_evaluated", action="commit", allowed=True, risk="low")
        return {"status": 200, "suite": suite, "total": 1, "passed": 1, "failed": 0, "cases": []}

    monkeypatch.setattr(run_eval_suite.case_loader, "run_suite", fake_run_suite)
    result = run_eval_suite.run_suite("phase7_backend_engines", "/tmp/repo", report_id="phase7_cli_unit")
    assert result["engine_score"] >= 80
    assert set(result["engine_subscores"]) == {"repo_intelligence", "workspace", "patch_engine", "test_quality_engine", "policy_engine"}
    assert result["result"]["status"] == 200
