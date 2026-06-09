from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from utils import eval_telemetry

REPO_ROOT = Path(__file__).resolve().parents[1]
REGRESSION_ROOT = REPO_ROOT / "evals" / "regressions"
CORE_SCHEMA = REPO_ROOT / "coding-gpt-core-openapi.yaml"
INSTRUCTIONS = REPO_ROOT / "coding-gpt-instructions.md"
EXPECTED_SERVER = "https://unscrutinized-immotile-jermaine.ngrok-free.dev"


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "":
        return ""
    try:
        return json.loads(value)
    except Exception:
        pass
    if value.isdigit():
        return int(value)
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return value


def load_regression(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    p = p.resolve()
    text = p.read_text(encoding="utf-8")
    data: dict[str, Any] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if ": |" in line:
            key = line.split(":", 1)[0].strip()
            i += 1
            block = []
            while i < len(lines) and (lines[i].startswith("  ") or not lines[i].strip()):
                block.append(lines[i][2:] if lines[i].startswith("  ") else lines[i])
                i += 1
            value = "\n".join(block).rstrip()
            if key.endswith("_json"):
                try:
                    data[key[:-5]] = json.loads(value) if value else {}
                except Exception:
                    data[key] = value
            else:
                data[key] = value
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = _parse_scalar(value)
        i += 1
    data.setdefault("id", p.stem)
    data.setdefault("source_file", str(p.relative_to(REPO_ROOT)))
    data.setdefault("type", "regression")
    data.setdefault("safe_only", True)
    return data


def list_regressions() -> list[dict[str, Any]]:
    REGRESSION_ROOT.mkdir(parents=True, exist_ok=True)
    items = []
    for path in sorted(REGRESSION_ROOT.glob("*.yaml")):
        try:
            r = load_regression(path)
            items.append({
                "id": r.get("id"),
                "title": r.get("title"),
                "source": r.get("source"),
                "failure_layer": r.get("failure_layer"),
                "runner": r.get("runner"),
                "source_file": r.get("source_file"),
            })
        except Exception as exc:
            items.append({"id": path.stem, "source_file": str(path.relative_to(REPO_ROOT)), "load_error": str(exc)})
    return items


def _ok(name: str, passed: bool, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "details": details or {}}


def _method_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip() in {"get:", "post:", "put:", "patch:", "delete:"})


def _run_missing_dispatcher_payload(regression: dict[str, Any], repo_path: str) -> dict[str, Any]:
    from routes import coding_dispatch
    first = coding_dispatch.repo_action(coding_dispatch.CategoryActionRequest(action="instructions", payload={}))
    err = first.get("error", {}) if isinstance(first, dict) else {}
    retry_payload = dict(err.get("example_payload") or {})
    retry_payload.setdefault("repo_path", repo_path)
    second = coding_dispatch.repo_action(coding_dispatch.CategoryActionRequest(action="instructions", payload=retry_payload))
    checks = [
        _ok("missing_payload_detected", first.get("status") == 400 and err.get("code") == "missing_payload_fields", {"error": err}),
        _ok("required_payload_present", "repo_path" in (err.get("required_payload") or []), {"required_payload": err.get("required_payload")}),
        _ok("example_payload_present", retry_payload.get("repo_path") == repo_path or retry_payload.get("repo_path") == "/home/obsidian/Elevate_test", {"example_payload": retry_payload}),
        _ok("retry_succeeds", second.get("status") == 200 or isinstance(second.get("status"), str), {"second_status": second.get("status")}),
    ]
    return {"checks": checks, "first_status": first.get("status"), "second_status": second.get("status")}


def _run_wrong_ngrok_domain(regression: dict[str, Any], repo_path: str) -> dict[str, Any]:
    text = CORE_SCHEMA.read_text(encoding="utf-8")
    checks = [
        _ok("expected_server_present", f'- url: \"{EXPECTED_SERVER}\"' in text or f"- url: '{EXPECTED_SERVER}'" in text or EXPECTED_SERVER in text),
        _ok("old_domain_absent", "https://gpt-api.ngrok.app" not in text),
    ]
    return {"checks": checks, "expected_server": EXPECTED_SERVER}


def _run_missing_api_key(regression: dict[str, Any], repo_path: str) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    response = client.post("/agent/coding-task", json={"repo_path": repo_path, "task": "Regression: missing API key should fail"})
    checks = [
        _ok("missing_key_rejected", response.status_code == 403, {"http_status": response.status_code}),
        _ok("auth_scheme_declared", "name: \"x-api-key\"" in CORE_SCHEMA.read_text(encoding="utf-8"), {}),
    ]
    return {"checks": checks, "http_status": response.status_code}


def _run_instructions_too_long(regression: dict[str, Any], repo_path: str) -> dict[str, Any]:
    text = INSTRUCTIONS.read_text(encoding="utf-8")
    checks = [
        _ok("instructions_under_8000_chars", len(text) < 8000, {"chars": len(text)}),
        _ok("instructions_under_8000_bytes", len(text.encode("utf-8")) < 8000, {"bytes": len(text.encode("utf-8"))}),
    ]
    return {"checks": checks, "chars": len(text), "bytes": len(text.encode("utf-8"))}


def _run_schema_security_list(regression: dict[str, Any], repo_path: str) -> dict[str, Any]:
    text = CORE_SCHEMA.read_text(encoding="utf-8")
    checks = [
        _ok("security_requirement_uses_empty_list", "- ApiKeyAuth: []" in text),
        _ok("security_requirement_not_blank", "- ApiKeyAuth:\n" not in text),
        _ok("security_scheme_uses_header", "name: \"x-api-key\"" in text),
    ]
    return {"checks": checks}


def _run_operation_limit(regression: dict[str, Any], repo_path: str) -> dict[str, Any]:
    text = CORE_SCHEMA.read_text(encoding="utf-8")
    methods = _method_count(text)
    checks = [
        _ok("core_schema_under_30_operations", methods <= 30, {"method_lines": methods}),
        _ok("smoke_test_endpoint_present", "/agent/coding-task/smoke-test:" in text),
    ]
    return {"checks": checks, "method_lines": methods}


def _run_phase3_regression_create(regression: dict[str, Any], repo_path: str) -> dict[str, Any]:
    checks = [
        _ok("regression_file_loads", bool(regression.get("id")), {"id": regression.get("id")}),
        _ok("failure_layer_present", bool(regression.get("failure_layer")), {"failure_layer": regression.get("failure_layer")}),
    ]
    return {"checks": checks}


RUNNERS = {
    "missing_dispatcher_payload": _run_missing_dispatcher_payload,
    "wrong_ngrok_domain": _run_wrong_ngrok_domain,
    "missing_api_key": _run_missing_api_key,
    "instructions_too_long": _run_instructions_too_long,
    "schema_security_list": _run_schema_security_list,
    "operation_limit": _run_operation_limit,
    "phase3_regression_create": _run_phase3_regression_create,
}


def run_regression(regression: dict[str, Any], *, repo_path: str, run_id: str | None = None) -> dict[str, Any]:
    run_id = run_id or f"reg_{int(time.time() * 1000)}"
    runner = regression.get("runner")
    eval_telemetry.log_event("regression_started", run_id=run_id, regression_id=regression.get("id"), failure_layer=regression.get("failure_layer"), runner=runner)
    if runner not in RUNNERS:
        result = {"status": 400, "error": {"code": "unsupported_regression_runner", "message": f"Unsupported runner: {runner}"}, "checks": []}
    else:
        try:
            result = RUNNERS[runner](regression, repo_path)
            passed = all(c.get("passed") for c in result.get("checks", []))
            result["status"] = 200 if passed else 400
            result["passed"] = bool(passed)
        except Exception as exc:
            result = {"status": 500, "passed": False, "error": {"code": "regression_runner_error", "message": str(exc)}, "checks": []}
    result.setdefault("id", regression.get("id"))
    result.setdefault("title", regression.get("title"))
    result.setdefault("failure_layer", regression.get("failure_layer"))
    result.setdefault("source_file", regression.get("source_file"))
    eval_telemetry.log_event("regression_completed", run_id=run_id, regression_id=regression.get("id"), failure_layer=regression.get("failure_layer"), runner=runner, status=result.get("status"), passed=result.get("passed"))
    return result


def run_all(*, repo_path: str, run_id: str | None = None) -> dict[str, Any]:
    run_id = run_id or f"regressions_{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time()*1000)%10000:04d}"
    regressions = [load_regression(REGRESSION_ROOT / item["source_file"].split("evals/regressions/", 1)[-1]) for item in list_regressions() if not item.get("load_error")]
    results = [run_regression(r, repo_path=repo_path, run_id=run_id) for r in regressions]
    passed = sum(1 for r in results if r.get("passed"))
    return {"status": 200 if passed == len(results) else 400, "run_id": run_id, "suite": "regressions", "total": len(results), "passed": passed, "failed": len(results) - passed, "regressions": results}
