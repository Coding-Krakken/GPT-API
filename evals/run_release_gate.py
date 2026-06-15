from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals import case_loader, regression_loader, report as eval_report
from utils import eval_telemetry

DEFAULT_REPO = "/home/obsidian/Elevate_test"
EXPECTED_SERVER = "https://unscrutinized-immotile-jermaine.ngrok-free.dev"
CORE_SCHEMA = REPO_ROOT / "coding-gpt-core-openapi.yaml"
FULL_SCHEMA = REPO_ROOT / "coding-openapi.yaml"
INSTRUCTIONS = REPO_ROOT / "coding-gpt-instructions.md"
KNOWLEDGE_FILES = [
    REPO_ROOT / "knowledge" / "CODING_GPT_WORKFLOW.md",
    REPO_ROOT / "knowledge" / "CODING_GPT_DISPATCHERS.md",
    REPO_ROOT / "knowledge" / "CODING_GPT_TROUBLESHOOTING.md",
    REPO_ROOT / "knowledge" / "CODING_GPT_EVALUATION.md",
]
FORBIDDEN_PREFIXES = ("/shell", "/files", "/manageFiles", "/package", "/apps", "/monitor", "/git", "/batch", "/gpts", "/dispatch")
FORBIDDEN_MARKERS = ("runShellCommand", "manageFiles", "packageManager", "appControl")
METHOD_LINES = {"get:", "post:", "put:", "patch:", "delete:"}


def _now_id() -> str:
    return f"release_gate_{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time() * 1000) % 10000:04d}"


def _ok(name: str, passed: bool, details: dict[str, Any] | None = None, severity: str = "blocker") -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "severity": severity, "details": details or {}}


def _method_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip() in METHOD_LINES)


def _schema_paths(text: str) -> list[str]:
    paths: list[str] = []
    in_paths = False
    for line in text.splitlines():
        if line.strip() == "paths:":
            in_paths = True
            continue
        if in_paths and line and not line.startswith(" ") and line.strip().endswith(":"):
            break
        if in_paths and line.startswith("  /") and line.rstrip().endswith(":"):
            paths.append(line.strip()[:-1])
    return paths


def _schema_checks() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    core_text = CORE_SCHEMA.read_text(encoding="utf-8") if CORE_SCHEMA.exists() else ""
    full_text = FULL_SCHEMA.read_text(encoding="utf-8") if FULL_SCHEMA.exists() else ""
    core_ops = _method_count(core_text)
    paths = _schema_paths(core_text)
    forbidden_paths = [p for p in paths if any(p == fp or p.startswith(fp + "/") for fp in FORBIDDEN_PREFIXES)]
    forbidden_markers = [m for m in FORBIDDEN_MARKERS if m in core_text]
    checks.extend([
        _ok("core_schema_exists", CORE_SCHEMA.exists(), {"path": str(CORE_SCHEMA)}),
        _ok("full_schema_exists", FULL_SCHEMA.exists(), {"path": str(FULL_SCHEMA)}),
        _ok("core_schema_under_30_operations", core_ops <= 30, {"operation_count": core_ops, "limit": 30}),
        _ok("core_schema_has_expected_server", f'- url: \"{EXPECTED_SERVER}\"' in core_text or EXPECTED_SERVER in core_text, {"expected_server": EXPECTED_SERVER}),
        _ok("old_ngrok_domain_absent", "https://gpt-api.ngrok.app" not in core_text and "https://gpt-api.ngrok.app" not in full_text),
        _ok("api_key_auth_scheme_present", "ApiKeyAuth:" in core_text and "name: \"x-api-key\"" in core_text and "in: \"header\"" in core_text),
        _ok("api_key_security_requirement_is_list", "- ApiKeyAuth: []" in core_text and "- ApiKeyAuth:\n" not in core_text),
        _ok("smoke_test_endpoint_present", "/agent/coding-task/smoke-test:" in core_text),
        _ok("dispatcher_payload_required_in_schema", "payload:" in core_text and "Never omit this" in core_text),
        _ok("forbidden_operator_paths_absent", not forbidden_paths, {"forbidden_paths": forbidden_paths}),
        _ok("forbidden_operator_markers_absent", not forbidden_markers, {"forbidden_markers": forbidden_markers}),
    ])
    return checks


def _instruction_checks() -> list[dict[str, Any]]:
    text = INSTRUCTIONS.read_text(encoding="utf-8") if INSTRUCTIONS.exists() else ""
    missing_knowledge = [str(p.relative_to(REPO_ROOT)) for p in KNOWLEDGE_FILES if not p.exists()]
    return [
        _ok("instructions_file_exists", INSTRUCTIONS.exists(), {"path": str(INSTRUCTIONS)}),
        _ok("instructions_under_8000_chars", len(text) < 8000, {"chars": len(text), "limit": 8000}),
        _ok("instructions_under_8000_bytes", len(text.encode("utf-8")) < 8000, {"bytes": len(text.encode("utf-8")), "limit": 8000}),
        _ok("instructions_include_smoke_test_rule", "/agent/coding-task/smoke-test" in text),
        _ok("instructions_include_payload_rule", "Every dispatcher call must include" in text and "missing_payload_fields" in text),
        _ok("knowledge_files_present", not missing_knowledge, {"missing": missing_knowledge}),
    ]


def _git_checks() -> list[dict[str, Any]]:
    def run(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(args, cwd=REPO_ROOT, text=True, capture_output=True, timeout=30)
    checks: list[dict[str, Any]] = []
    status = run(["git", "status", "--short"])
    head = run(["git", "rev-parse", "--short", "HEAD"])
    remote = run(["git", "ls-remote", "origin", "feature/coding-gpt-safe-agent"])
    head_full = run(["git", "rev-parse", "HEAD"])
    remote_hash = (remote.stdout.strip().split()[0] if remote.stdout.strip() else "")
    checks.append(_ok("git_worktree_clean_before_gate", status.returncode == 0 and status.stdout.strip() == "", {"status": status.stdout.strip()}))
    checks.append(_ok("git_remote_branch_matches_head", head_full.returncode == 0 and bool(remote_hash) and remote_hash == head_full.stdout.strip(), {"head": head_full.stdout.strip(), "remote": remote_hash, "short_head": head.stdout.strip()}))
    return checks


def _run_compile_check() -> dict[str, Any]:
    proc = subprocess.run([sys.executable, "-m", "py_compile", "main.py", *[str(p) for p in sorted((REPO_ROOT / "utils").glob("*.py"))], *[str(p) for p in sorted((REPO_ROOT / "routes").glob("*.py"))]], cwd=REPO_ROOT, text=True, capture_output=True, timeout=120)
    return _ok("python_compile_check", proc.returncode == 0, {"returncode": proc.returncode, "stdout_tail": proc.stdout[-1000:], "stderr_tail": proc.stderr[-2000:]})


def _run_suite_checks(repo_path: str, run_id: str) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    eval_telemetry.log_event("release_gate_suite_started", run_id=run_id, suite="release_gate", repo_path=repo_path)
    suite = case_loader.run_suite("release_gate", repo_path=repo_path, run_id=run_id)
    eval_telemetry.log_event("release_gate_suite_completed", run_id=run_id, suite="release_gate", repo_path=repo_path, status=suite.get("status"), passed=suite.get("failed") == 0)
    eval_telemetry.log_event("release_gate_regressions_started", run_id=run_id, suite="regressions", repo_path=repo_path)
    regressions = regression_loader.run_all(repo_path=repo_path, run_id=run_id)
    eval_telemetry.log_event("release_gate_regressions_completed", run_id=run_id, suite="regressions", repo_path=repo_path, status=regressions.get("status"), passed=regressions.get("failed") == 0)
    checks = [
        _ok("release_gate_suite_passed", suite.get("status") == 200 and suite.get("failed") == 0, {"total": suite.get("total"), "passed": suite.get("passed"), "failed": suite.get("failed")}),
        _ok("regression_suite_passed", regressions.get("status") == 200 and regressions.get("failed") == 0, {"total": regressions.get("total"), "passed": regressions.get("passed"), "failed": regressions.get("failed")}),
    ]
    return checks, suite, regressions


def _write_release_gate_report(result: dict[str, Any]) -> tuple[Path, Path]:
    root = eval_telemetry.eval_root() / "release_gates"
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / f"{result['run_id']}.json"
    md_path = root / f"{result['run_id']}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    rows = []
    for c in result["checks"]:
        rows.append(f"| {'PASS' if c['passed'] else 'FAIL'} | {c['name']} | {c['severity']} | `{json.dumps(c.get('details', {}), sort_keys=True)[:500]}` |")
    md = "\n".join([
        f"# Coding GPT Release Gate: {result['run_id']}",
        "",
        "## Summary",
        "",
        f"- Status: **{result['status']}**",
        f"- Repo path: `{result['repo_path']}`",
        f"- Total checks: {result['total']}",
        f"- Passed: {result['passed']}",
        f"- Failed: {result['failed']}",
        f"- Agent score: {result.get('eval_report', {}).get('agent_score')}",
        f"- Backend score: {result.get('eval_report', {}).get('backend_score')}",
        "",
        "## Checks",
        "",
        "| Result | Check | Severity | Details |",
        "|---|---|---|---|",
        *rows,
        "",
        "## Artifacts",
        "",
        f"- Eval report JSON: `{result.get('eval_report', {}).get('report_json')}`",
        f"- Eval report MD: `{result.get('eval_report', {}).get('report_md')}`",
        f"- Release gate JSON: `{json_path}`",
        f"- Release gate MD: `{md_path}`",
        "",
    ])
    md_path.write_text(md, encoding="utf-8")
    return json_path, md_path


def run_release_gate(repo_path: str, *, run_id: str | None = None, require_clean_git: bool = True) -> dict[str, Any]:
    run_id = run_id or _now_id()
    start_ms = int(time.time() * 1000)
    checks: list[dict[str, Any]] = []
    eval_telemetry.log_event("release_gate_started", run_id=run_id, repo_path=repo_path)
    if require_clean_git:
        checks.extend(_git_checks())
    checks.extend(_schema_checks())
    checks.extend(_instruction_checks())
    checks.append(_run_compile_check())
    suite_checks, suite, regressions = _run_suite_checks(repo_path, run_id)
    checks.extend(suite_checks)
    events = [e for e in eval_report.load_events() if isinstance(e.get("timestamp"), int) and e.get("timestamp") >= start_ms and e.get("run_id") in (None, run_id)]
    report = eval_report.build_report(events, report_id=run_id, source_path=str(eval_telemetry.events_path()))
    report_json = eval_report.write_json_report(report)
    report_md = eval_report.write_markdown_report(report)
    report["summary"]["report_json"] = str(report_json)
    report["summary"]["report_md"] = str(report_md)
    report_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    agent_score = int(report.get("scores", {}).get("agent", {}).get("score") or 0)
    backend_score = int(report.get("scores", {}).get("backend", {}).get("score") or 0)
    checks.append(_ok("agent_readiness_score_at_least_80", agent_score >= 80, {"agent_score": agent_score}, severity="warning"))
    checks.append(_ok("backend_score_at_least_80", backend_score >= 80, {"backend_score": backend_score}, severity="warning"))
    failed_checks = [c for c in checks if not c["passed"] and c.get("severity") == "blocker"]
    status = 200 if not failed_checks else 400
    eval_telemetry.log_event("release_gate_completed", run_id=run_id, repo_path=repo_path, status=status, passed=status == 200, failed_checks=len(failed_checks), agent_score=agent_score, backend_score=backend_score)
    result = {
        "status": status,
        "run_id": run_id,
        "repo_path": repo_path,
        "total": len(checks),
        "passed": sum(1 for c in checks if c["passed"]),
        "failed": sum(1 for c in checks if not c["passed"]),
        "failed_blockers": failed_checks,
        "checks": checks,
        "suite_result": suite,
        "regression_result": regressions,
        "eval_report": {"agent_score": agent_score, "backend_score": backend_score, "report_json": str(report_json), "report_md": str(report_md)},
    }
    gate_json, gate_md = _write_release_gate_report(result)
    result["release_gate_json"] = str(gate_json)
    result["release_gate_md"] = str(gate_md)
    gate_json.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Coding GPT Phase 9 release gate")
    parser.add_argument("--repo-path", default=DEFAULT_REPO)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--allow-dirty", action="store_true", help="Skip clean/pushed git checks. Intended only while developing the gate itself.")
    args = parser.parse_args(argv)
    result = run_release_gate(args.repo_path, run_id=args.run_id, require_clean_git=not args.allow_dirty)
    print(json.dumps({
        "status": result["status"],
        "run_id": result["run_id"],
        "total": result["total"],
        "passed": result["passed"],
        "failed": result["failed"],
        "failed_blockers": [c["name"] for c in result["failed_blockers"]],
        "agent_score": result["eval_report"]["agent_score"],
        "backend_score": result["eval_report"]["backend_score"],
        "release_gate_json": result["release_gate_json"],
        "release_gate_md": result["release_gate_md"],
        "eval_report_json": result["eval_report"]["report_json"],
        "eval_report_md": result["eval_report"]["report_md"],
    }, indent=2))
    return 0 if result["status"] == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
