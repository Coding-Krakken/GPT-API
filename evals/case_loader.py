from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from utils import eval_telemetry

REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_ROOT = REPO_ROOT / "evals" / "cases"


def load_case(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    p = p.resolve()
    data = json.loads(p.read_text(encoding="utf-8"))
    data.setdefault("id", p.stem)
    data.setdefault("source_file", str(p.relative_to(REPO_ROOT)))
    return data


def list_cases() -> list[dict[str, Any]]:
    CASE_ROOT.mkdir(parents=True, exist_ok=True)
    cases = []
    for path in sorted(CASE_ROOT.glob("*.yaml")):
        try:
            case = load_case(path)
            cases.append({
                "id": case.get("id"),
                "suite": case.get("suite"),
                "type": case.get("type"),
                "title": case.get("title"),
                "safe_only": case.get("safe_only", True),
                "source_file": case.get("source_file"),
                "runner": case.get("runner"),
            })
        except Exception as exc:
            cases.append({"id": path.stem, "source_file": str(path.relative_to(REPO_ROOT)), "load_error": str(exc)})
    return cases


def cases_for_suite(suite: str) -> list[dict[str, Any]]:
    return [load_case(CASE_ROOT / c["source_file"].split("evals/cases/", 1)[-1]) for c in list_cases() if not c.get("load_error") and (c.get("suite") == suite or c.get("id") == suite)]


def _ok(name: str, passed: bool, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "details": details or {}}


def _run_core_smoke(case: dict[str, Any], repo_path: str, run_id: str) -> dict[str, Any]:
    from routes.coding_agent import CodingTaskSmokeTestRequest, coding_task_smoke_test
    body = coding_task_smoke_test(CodingTaskSmokeTestRequest(
        repo_path=repo_path,
        safe_only=True,
        task=f"Eval case {case['id']} safe core smoke {run_id}",
    ))
    smoke = body.get("smoke_test", {}) if isinstance(body, dict) else {}
    checks = [
        _ok("http_status", body.get("status") == 200, {"status": body.get("status")}),
        _ok("all_core_checks_pass", smoke.get("failed") == 0 and smoke.get("passed") == smoke.get("total"), {"total": smoke.get("total"), "passed": smoke.get("passed"), "failed": smoke.get("failed")}),
    ]
    return {"status": 200 if all(c["passed"] for c in checks) else 400, "checks": checks, "raw": body}


def _run_payload_recovery(case: dict[str, Any], repo_path: str, run_id: str) -> dict[str, Any]:
    from routes import coding_dispatch
    first = coding_dispatch.repo_action(coding_dispatch.CategoryActionRequest(action="instructions", payload={}))
    err = first.get("error", {}) if isinstance(first, dict) else {}
    retry_payload = dict(err.get("example_payload") or {})
    retry_payload.setdefault("repo_path", repo_path)
    second = coding_dispatch.repo_action(coding_dispatch.CategoryActionRequest(action="instructions", payload=retry_payload))
    checks = [
        _ok("missing_payload_detected", first.get("status") == 400 and err.get("code") == "missing_payload_fields", {"first_status": first.get("status"), "error": err}),
        _ok("example_payload_present", "repo_path" in retry_payload, {"retry_payload": retry_payload}),
        _ok("corrected_retry_succeeds", second.get("status") == 200 or isinstance(second.get("status"), str), {"second_status": second.get("status")}),
    ]
    return {"status": 200 if all(c["passed"] for c in checks) else 400, "checks": checks, "first_call": first, "retry_payload": retry_payload, "second_call_status": second.get("status")}


def _create_workspace(repo_path: str, task: str):
    from routes.coding_agent import CodingTaskRequest, coding_task
    body = coding_task(CodingTaskRequest(repo_path=repo_path, task=task, max_iterations=1, create_pr=False))
    task_id = body.get("task", {}).get("task_id") if isinstance(body, dict) else None
    workspace_path = body.get("workspace", {}).get("workspace_path") if isinstance(body, dict) else None
    return body, task_id, workspace_path


def _run_quality_missing_dependency(case: dict[str, Any], repo_path: str, run_id: str) -> dict[str, Any]:
    from routes import coding_dispatch
    init, task_id, workspace_path = _create_workspace(repo_path, f"Eval case {case['id']} quality check {run_id}")
    result = coding_dispatch.quality_action(coding_dispatch.CategoryActionRequest(action="check", payload={"workspace_path": workspace_path, "timeout_seconds": 60})) if workspace_path else {"status": 500, "error": {"code": "workspace_missing"}}
    quality_results = result.get("results", []) if isinstance(result, dict) else []
    saw_dependency_signal = any((r.get("exit_code") == 127 or "not found" in (r.get("stderr_tail") or "").lower()) for r in quality_results if isinstance(r, dict))
    checks = [
        _ok("workspace_created", bool(workspace_path), {"task_id": task_id, "workspace_path": workspace_path}),
        _ok("quality_endpoint_responded", result.get("status") == 200, {"status": result.get("status")}),
        _ok("quality_result_structured", isinstance(quality_results, list), {"result_count": len(quality_results)}),
    ]
    return {"status": 200 if all(c["passed"] for c in checks) else 400, "checks": checks, "dependency_missing_signal": saw_dependency_signal, "quality_result": result}


def _run_policy_block_secret(case: dict[str, Any], repo_path: str, run_id: str) -> dict[str, Any]:
    from routes import coding_dispatch
    secret_path = str(Path(repo_path) / ".env")
    result = coding_dispatch.policy_action(coding_dispatch.CategoryActionRequest(action="check", payload={"path": secret_path, "repo_root": repo_path}))
    checks = [
        _ok("policy_endpoint_responded", result.get("status") == 200, {"status": result.get("status")}),
        _ok("secret_path_blocked", result.get("allowed") is False, {"allowed": result.get("allowed"), "error": result.get("error"), "reasons": result.get("reasons")}),
    ]
    return {"status": 200 if all(c["passed"] for c in checks) else 400, "checks": checks, "policy_result": result}


def _run_final_answer_contract(case: dict[str, Any], repo_path: str, run_id: str) -> dict[str, Any]:
    from routes.coding_agent import CodingTaskContractReportRequest, coding_task_contract_report
    init, task_id, workspace_path = _create_workspace(repo_path, f"Eval case {case['id']} contract report {run_id}")
    report = coding_task_contract_report(CodingTaskContractReportRequest(task_id=task_id)) if task_id else {"status": 500, "error": {"code": "task_missing"}}
    validation = report.get("validation", {}) if isinstance(report, dict) else {}
    checks = [
        _ok("task_created", bool(task_id), {"task_id": task_id, "workspace_path": workspace_path}),
        _ok("contract_report_responded", report.get("status") == 200, {"status": report.get("status")}),
        _ok("missing_artifacts_reported", validation.get("valid") is False and bool(validation.get("missing")), {"missing": validation.get("missing")}),
    ]
    return {"status": 200 if all(c["passed"] for c in checks) else 400, "checks": checks, "contract_report": report}


def run_case(case: dict[str, Any], *, repo_path: str, run_id: str | None = None) -> dict[str, Any]:
    run_id = run_id or f"case_{case.get('id')}_{int(time.time() * 1000)}"
    runner = case.get("runner")
    eval_telemetry.log_event("eval_case_started", run_id=run_id, case_id=case.get("id"), suite=case.get("suite"), repo_path=repo_path, runner=runner)
    try:
        if runner == "core_smoke":
            result = _run_core_smoke(case, repo_path, run_id)
        elif runner == "payload_recovery":
            result = _run_payload_recovery(case, repo_path, run_id)
        elif runner == "quality_missing_dependency":
            result = _run_quality_missing_dependency(case, repo_path, run_id)
        elif runner == "policy_block_secret":
            result = _run_policy_block_secret(case, repo_path, run_id)
        elif runner == "final_answer_contract":
            result = _run_final_answer_contract(case, repo_path, run_id)
        else:
            result = {"status": 400, "error": {"code": "unsupported_case_runner", "message": f"Unsupported runner: {runner}"}, "checks": []}
    except Exception as exc:
        result = {"status": 500, "error": {"code": "case_runner_error", "message": str(exc)}, "checks": []}
    passed = result.get("status") == 200 and all(c.get("passed") for c in result.get("checks", []))
    eval_telemetry.log_event("eval_case_completed", run_id=run_id, case_id=case.get("id"), suite=case.get("suite"), repo_path=repo_path, runner=runner, status=result.get("status"), passed=passed)
    result.setdefault("case_id", case.get("id"))
    result.setdefault("suite", case.get("suite"))
    result["passed"] = bool(passed)
    return result


def run_suite(suite: str, *, repo_path: str, run_id: str | None = None) -> dict[str, Any]:
    selected = cases_for_suite(suite)
    if not selected:
        return {"status": 404, "error": {"code": "suite_not_found", "message": f"No declarative cases found for suite or case id: {suite}"}, "cases": []}
    results = [run_case(case, repo_path=repo_path, run_id=run_id) for case in selected]
    passed = sum(1 for r in results if r.get("passed"))
    return {"status": 200 if passed == len(results) else 400, "suite": suite, "total": len(results), "passed": passed, "failed": len(results) - passed, "cases": results}
