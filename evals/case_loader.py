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
                "suites": case.get("suites", [case.get("suite")] if case.get("suite") else []),
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
    selected = []
    for c in list_cases():
        if c.get("load_error"):
            continue
        suites = set(c.get("suites") or [])
        if c.get("suite"):
            suites.add(c.get("suite"))
        if c.get("id") == suite or suite in suites:
            selected.append(load_case(CASE_ROOT / c["source_file"].split("evals/cases/", 1)[-1]))
    return selected


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




def _run_repo_intelligence(case: dict[str, Any], repo_path: str, run_id: str) -> dict[str, Any]:
    from routes import coding_dispatch
    overview = coding_dispatch.repo_action(coding_dispatch.CategoryActionRequest(action="overview", payload={"repo_path": repo_path, "max_depth": 2}))
    instructions = coding_dispatch.repo_action(coding_dispatch.CategoryActionRequest(action="instructions", payload={"repo_path": repo_path}))
    relevant = coding_dispatch.repo_action(coding_dispatch.CategoryActionRequest(action="relevant_context", payload={"repo_path": repo_path, "task": "Evaluate repo intelligence for a TypeScript app", "max_files": 8}))
    test_map = coding_dispatch.repo_action(coding_dispatch.CategoryActionRequest(action="test_map", payload={"repo_path": repo_path}))
    route_map = coding_dispatch.repo_action(coding_dispatch.CategoryActionRequest(action="route_map", payload={"repo_path": repo_path}))
    checks = [
        _ok("overview_responded", overview.get("status") == 200, {"status": overview.get("status")}),
        _ok("repo_detected", overview.get("is_git_repo") is True, {"is_git_repo": overview.get("is_git_repo")}),
        _ok("language_detected", bool(overview.get("languages")), {"languages": overview.get("languages")}),
        _ok("instructions_responded", instructions.get("status") == 200 or isinstance(instructions.get("status"), str), {"status": instructions.get("status")}),
        _ok("relevant_context_responded", relevant.get("status") == 200, {"status": relevant.get("status")}),
        _ok("test_map_responded", test_map.get("status") == 200, {"status": test_map.get("status")}),
        _ok("route_map_responded", route_map.get("status") == 200, {"status": route_map.get("status")}),
    ]
    return {"status": 200 if all(c["passed"] for c in checks) else 400, "checks": checks, "overview": overview}


def _fixture_repo(root: Path) -> None:
    import subprocess
    root.mkdir(parents=True, exist_ok=True)
    (root / "mathlib.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']\n", encoding="utf-8")
    (root / "tests").mkdir(exist_ok=True)
    (root / "tests" / "test_mathlib.py").write_text("from mathlib import add\n\ndef test_add():\n    assert add(2, 3) == 5\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.email", "eval@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Eval Runner"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "fixture"], cwd=root, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _run_simple_bugfix(case: dict[str, Any], repo_path: str, run_id: str) -> dict[str, Any]:
    import shutil
    from pathlib import Path
    from routes.coding_agent import CodingTaskRequest, coding_task
    from routes import coding_dispatch
    base = Path("/tmp/gpt-api-evals/fixtures") / f"simple_bugfix_{run_id}".replace("/", "_")
    if base.exists():
        shutil.rmtree(base)
    _fixture_repo(base)
    init = coding_task(CodingTaskRequest(repo_path=str(base), task="Fix add() so the known unit test passes", max_iterations=1, create_pr=False))
    task_id = init.get("task", {}).get("task_id") if isinstance(init, dict) else None
    workspace = init.get("workspace", {}).get("workspace_path") if isinstance(init, dict) else None
    patch = "diff --git a/mathlib.py b/mathlib.py\n--- a/mathlib.py\n+++ b/mathlib.py\n@@ -1,2 +1,2 @@\n def add(a, b):\n-    return a - b\n+    return a + b\n"
    preview = coding_dispatch.patch_action(coding_dispatch.CategoryActionRequest(action="preview", payload={"workspace_path": workspace, "patch": patch})) if workspace else {"status": 500}
    applied = coding_dispatch.patch_action(coding_dispatch.CategoryActionRequest(action="apply_recorded", payload={"workspace_path": workspace, "patch": patch, "task_id": task_id, "label": "simple_bugfix_eval"})) if workspace else {"status": 500}
    quality = coding_dispatch.quality_action(coding_dispatch.CategoryActionRequest(action="check", payload={"workspace_path": workspace, "timeout_seconds": 60})) if workspace else {"status": 500}
    diff_summary = coding_dispatch.workspace_action(coding_dispatch.CategoryActionRequest(action="diff_summary", payload={"workspace_path": workspace})) if workspace else {"status": 500}
    changed_files = [f.get("file") for f in diff_summary.get("files", []) if isinstance(f, dict)]
    checks = [
        _ok("fixture_workspace_created", bool(workspace), {"task_id": task_id, "workspace": workspace}),
        _ok("patch_preview_applies", preview.get("applies") is True or preview.get("status") == 200, {"status": preview.get("status"), "applies": preview.get("applies")}),
        _ok("patch_applied", applied.get("applied") is True or applied.get("status") == 200, {"status": applied.get("status"), "applied": applied.get("applied")}),
        _ok("minimal_one_file_change", changed_files == ["mathlib.py"] or len(changed_files) <= 1, {"changed_files": changed_files}),
        _ok("quality_endpoint_responded", quality.get("status") == 200, {"status": quality.get("status"), "passed": quality.get("passed")}),
    ]
    return {"status": 200 if all(c["passed"] for c in checks) else 400, "checks": checks, "task_id": task_id, "workspace_path": workspace, "changed_files": changed_files, "quality": quality}


def _run_backend_engine_metrics(case: dict[str, Any], repo_path: str, run_id: str) -> dict[str, Any]:
    from evals.engine_metrics import engine_metrics, engine_scores
    from evals import report as eval_report
    from routes.coding_agent import CodingTaskSmokeTestRequest, coding_task_smoke_test
    start_ms = int(time.time() * 1000)
    smoke = coding_task_smoke_test(CodingTaskSmokeTestRequest(
        repo_path=repo_path,
        safe_only=True,
        task=f"Phase 7 backend engine metrics validation {run_id}",
    ))
    events = [e for e in eval_report.load_events() if isinstance(e.get("timestamp"), int) and e.get("timestamp") >= start_ms]
    metrics = engine_metrics(events)
    scores = engine_scores(metrics)
    checks = [
        _ok("smoke_passed", smoke.get("status") == 200 and (smoke.get("smoke_test") or {}).get("failed") == 0, {"status": smoke.get("status"), "smoke": smoke.get("smoke_test", {})}),
        _ok("repo_metrics_present", metrics["repo_intelligence"].get("overview_count", 0) > 0, metrics["repo_intelligence"]),
        _ok("workspace_metrics_present", metrics["workspace"].get("created_count", 0) > 0, metrics["workspace"]),
        _ok("test_quality_metrics_present", metrics["test_quality_engine"].get("test_discovery_count", 0) > 0 or metrics["test_quality_engine"].get("quality_run_count", 0) > 0, metrics["test_quality_engine"]),
        _ok("policy_metrics_present", metrics["policy_engine"].get("policy_event_count", 0) > 0 or metrics["policy_engine"].get("path_check_count", 0) > 0, metrics["policy_engine"]),
        _ok("engine_scores_present", scores.get("overall") is not None and bool(scores.get("subscores")), scores),
    ]
    return {"status": 200 if all(c["passed"] for c in checks) else 400, "checks": checks, "engine_metrics": metrics, "engine_scores": scores}


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
        elif runner == "repo_intelligence":
            result = _run_repo_intelligence(case, repo_path, run_id)
        elif runner in {"simple_bugfix", "fixture_planned"}:
            result = _run_simple_bugfix(case, repo_path, run_id)
        elif runner == "backend_engine_metrics":
            result = _run_backend_engine_metrics(case, repo_path, run_id)
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
