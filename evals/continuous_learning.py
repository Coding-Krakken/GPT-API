from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals import dashboard as eval_dashboard
from evals import regression_loader
from evals.run_release_gate import run_release_gate
from utils import eval_telemetry

DEFAULT_REPO = "/home/obsidian/Elevate_test"
KNOWN_FAILURE_REGRESSIONS = {
    "missing_dispatcher_payload": "2026-06-09-missing-dispatcher-payload",
    "wrong_ngrok_domain": "2026-06-09-wrong-ngrok-domain",
    "missing_api_key": "2026-06-09-missing-api-key",
    "instructions_too_long": "2026-06-09-instructions-too-long",
    "operation_limit": "2026-06-09-operation-limit",
    "schema_security_list": "2026-06-09-schema-security-list",
}


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=REPO_ROOT, text=True, capture_output=True, timeout=30)


def _git_state() -> dict[str, Any]:
    status = _run_git(["git", "status", "--short"])
    branch = _run_git(["git", "status", "-sb"])
    head = _run_git(["git", "rev-parse", "HEAD"])
    short = _run_git(["git", "rev-parse", "--short", "HEAD"])
    remote = _run_git(["git", "ls-remote", "origin", "feature/coding-gpt-safe-agent"])
    remote_hash = remote.stdout.strip().split()[0] if remote.stdout.strip() else ""
    return {
        "clean": status.returncode == 0 and status.stdout.strip() == "",
        "status_short": status.stdout.strip(),
        "branch_status": branch.stdout.strip(),
        "head": head.stdout.strip(),
        "short_head": short.stdout.strip(),
        "remote_hash": remote_hash,
        "remote_matches_head": bool(remote_hash) and remote_hash == head.stdout.strip(),
    }


def _latest_report_id(exclude: set[str] | None = None) -> str | None:
    exclude = exclude or set()
    listing = eval_dashboard.list_reports(limit=25)
    for item in listing.get("reports", []):
        report_id = item.get("report_id")
        if report_id and report_id not in exclude:
            return str(report_id)
    return None


def _regression_coverage() -> dict[str, Any]:
    regressions = regression_loader.list_regressions()
    ids = {str(item.get("id") or "") for item in regressions}
    files = {str(item.get("source_file") or "") for item in regressions}
    checks = []
    for key, expected in KNOWN_FAILURE_REGRESSIONS.items():
        present = any(expected in rid for rid in ids) or any(expected in f for f in files)
        checks.append({"failure": key, "expected_regression": expected, "present": present})
    missing = [c for c in checks if not c["present"]]
    return {"total_known_failures": len(checks), "covered": len(checks) - len(missing), "missing": missing, "checks": checks}


def _compare_reports(current_report_id: str | None, baseline_report_id: str | None) -> dict[str, Any] | None:
    if not current_report_id or not baseline_report_id or current_report_id == baseline_report_id:
        return None
    try:
        return eval_dashboard.compare(current_report_id, baseline_report_id)
    except Exception as exc:
        return {"status": 500, "error": {"code": "compare_failed", "message": str(exc)}}


def _extract_ship_decision(gate: dict[str, Any], comparison: dict[str, Any] | None, coverage: dict[str, Any], git_state: dict[str, Any], require_clean_git: bool) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    if gate.get("status") != 200:
        blockers.append("release_gate_failed")
    if coverage.get("missing"):
        blockers.append("known_failure_without_regression")
    if require_clean_git and not git_state.get("clean"):
        blockers.append("git_worktree_dirty")
    if require_clean_git and not git_state.get("remote_matches_head"):
        blockers.append("remote_not_pushed")
    if comparison and comparison.get("status") == 200:
        deltas = comparison.get("deltas", {})
        if deltas.get("failure_count", 0) > 0:
            blockers.append("new_failures_vs_baseline")
        if deltas.get("agent_score", 0) < -5:
            blockers.append("agent_score_regressed")
        if deltas.get("backend_score", 0) < -5:
            blockers.append("backend_score_regressed")
    elif comparison:
        warnings.append("baseline_comparison_unavailable")
    return {
        "ship_ready": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "rule": "Ship only when release gate passes, known failures have regressions, git is clean/pushed when required, and comparison shows no unacceptable regression.",
    }


def _write_cycle_report(result: dict[str, Any]) -> tuple[Path, Path]:
    root = eval_telemetry.eval_root() / "continuous_learning"
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / f"{result['run_id']}.json"
    md_path = root / f"{result['run_id']}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    decision = result.get("ship_decision", {})
    coverage = result.get("regression_coverage", {})
    comparison = result.get("comparison") or {}
    deltas = comparison.get("deltas", {}) if isinstance(comparison, dict) else {}
    lines = [
        f"# Coding GPT Continuous Learning Cycle: {result['run_id']}",
        "",
        "## Decision",
        "",
        f"- Ship ready: **{decision.get('ship_ready')}**",
        f"- Blockers: `{', '.join(decision.get('blockers') or []) or 'none'}`",
        f"- Warnings: `{', '.join(decision.get('warnings') or []) or 'none'}`",
        "",
        "## Release gate",
        "",
        f"- Status: `{result.get('release_gate', {}).get('status')}`",
        f"- Agent score: `{result.get('release_gate', {}).get('eval_report', {}).get('agent_score')}`",
        f"- Backend score: `{result.get('release_gate', {}).get('eval_report', {}).get('backend_score')}`",
        f"- Report: `{result.get('release_gate', {}).get('release_gate_md')}`",
        "",
        "## Baseline comparison",
        "",
        f"- Current report: `{result.get('current_report_id')}`",
        f"- Baseline report: `{result.get('baseline_report_id')}`",
        f"- Agent delta: `{deltas.get('agent_score')}`",
        f"- Backend delta: `{deltas.get('backend_score')}`",
        f"- Failure delta: `{deltas.get('failure_count')}`",
        "",
        "## Regression coverage",
        "",
        f"- Known failures covered: `{coverage.get('covered')}/{coverage.get('total_known_failures')}`",
        "",
        "| Failure | Regression | Present |",
        "|---|---|---|",
    ]
    for c in coverage.get("checks", []):
        lines.append(f"| {c.get('failure')} | `{c.get('expected_regression')}` | {c.get('present')} |")
    lines.extend([
        "",
        "## Operating loop",
        "",
        "1. Run real task or eval suite.",
        "2. Capture trace.",
        "3. Generate scorecard and recommendations.",
        "4. Convert every real failure into a regression case.",
        "5. Improve backend/schema/instructions/knowledge.",
        "6. Run release gate.",
        "7. Compare with baseline.",
        "8. Ship only if decision is ship-ready or tradeoff is explicitly documented.",
        "",
    ])
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def run_continuous_learning_cycle(
    repo_path: str = DEFAULT_REPO,
    *,
    run_id: str | None = None,
    baseline_report_id: str | None = None,
    require_clean_git: bool = True,
) -> dict[str, Any]:
    run_id = run_id or f"continuous_learning_{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time() * 1000) % 10000:04d}"
    eval_telemetry.log_event("continuous_learning_cycle_started", run_id=run_id, repo_path=repo_path)
    baseline_report_id = baseline_report_id or _latest_report_id()
    git_before = _git_state()
    gate = run_release_gate(repo_path, run_id=f"{run_id}_gate", require_clean_git=require_clean_git)
    current_report_id = None
    eval_report = gate.get("eval_report") or {}
    report_json = eval_report.get("report_json")
    if report_json:
        current_report_id = Path(report_json).stem
    comparison = _compare_reports(current_report_id, baseline_report_id)
    coverage = _regression_coverage()
    git_after = _git_state()
    decision = _extract_ship_decision(gate, comparison, coverage, git_after, require_clean_git)
    result = {
        "status": 200 if decision["ship_ready"] else 400,
        "run_id": run_id,
        "repo_path": repo_path,
        "baseline_report_id": baseline_report_id,
        "current_report_id": current_report_id,
        "git_before": git_before,
        "git_after": git_after,
        "release_gate": gate,
        "comparison": comparison,
        "regression_coverage": coverage,
        "ship_decision": decision,
    }
    json_path, md_path = _write_cycle_report(result)
    result["continuous_learning_json"] = str(json_path)
    result["continuous_learning_md"] = str(md_path)
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    eval_telemetry.log_event("continuous_learning_cycle_completed", run_id=run_id, repo_path=repo_path, status=result["status"], ship_ready=decision["ship_ready"], blockers=decision.get("blockers"))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Coding GPT Phase 12 continuous learning cycle")
    parser.add_argument("--repo-path", default=DEFAULT_REPO)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--baseline-report-id", default=None)
    parser.add_argument("--allow-dirty", action="store_true", help="Skip clean/pushed git enforcement while developing the cycle itself.")
    args = parser.parse_args(argv)
    result = run_continuous_learning_cycle(args.repo_path, run_id=args.run_id, baseline_report_id=args.baseline_report_id, require_clean_git=not args.allow_dirty)
    print(json.dumps({
        "status": result["status"],
        "run_id": result["run_id"],
        "ship_ready": result["ship_decision"]["ship_ready"],
        "blockers": result["ship_decision"].get("blockers"),
        "warnings": result["ship_decision"].get("warnings"),
        "current_report_id": result.get("current_report_id"),
        "baseline_report_id": result.get("baseline_report_id"),
        "continuous_learning_json": result.get("continuous_learning_json"),
        "continuous_learning_md": result.get("continuous_learning_md"),
    }, indent=2))
    return 0 if result["status"] == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
