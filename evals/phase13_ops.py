from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals import dashboard as eval_dashboard
from evals.continuous_learning import run_continuous_learning_cycle
from utils import eval_telemetry

DEFAULT_REPO = "/home/obsidian/Elevate_test"
EXPECTED_SERVER = "https://unscrutinized-immotile-jermaine.ngrok-free.dev"
PHASE13_VERSION = "phase13_production_ops_v1"

STATIC_ARTIFACTS = [
    "coding-gpt-core-openapi.yaml",
    "coding-openapi.yaml",
    "coding-gpt-instructions.md",
    "docs/CODING_GPT_EVAL_PLAN.md",
    "docs/CODING_GPT_SCORECARDS.md",
    "docs/CODING_GPT_PHASE9_RELEASE_GATE.md",
    "docs/CODING_GPT_PHASE12_CONTINUOUS_LEARNING.md",
    "docs/CODING_GPT_PHASE13_PRODUCTION_OPS.md",
    "knowledge/CODING_GPT_WORKFLOW.md",
    "knowledge/CODING_GPT_DISPATCHERS.md",
    "knowledge/CODING_GPT_TROUBLESHOOTING.md",
    "knowledge/CODING_GPT_EVALUATION.md",
]


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
    listing = eval_dashboard.list_reports(limit=50)
    for item in listing.get("reports", []):
        report_id = item.get("report_id")
        if report_id and report_id not in exclude:
            return str(report_id)
    return None


def _read_text(path: str) -> str:
    p = REPO_ROOT / path
    return p.read_text(encoding="utf-8") if p.exists() else ""


def operational_readiness(*, require_clean_git: bool = True) -> dict[str, Any]:
    core = _read_text("coding-gpt-core-openapi.yaml")
    instructions = _read_text("coding-gpt-instructions.md")
    knowledge_missing = [p for p in STATIC_ARTIFACTS if p.startswith("knowledge/") and not (REPO_ROOT / p).exists()]
    docs_missing = [p for p in STATIC_ARTIFACTS if p.startswith("docs/") and not (REPO_ROOT / p).exists()]
    method_lines = {"get:", "post:", "put:", "patch:", "delete:"}
    core_ops = sum(1 for line in core.splitlines() if line.strip() in method_lines)
    git_state = _git_state()
    checks = [
        {"name": "phase13_version_present", "passed": True, "details": {"version": PHASE13_VERSION}},
        {"name": "core_schema_under_30_operations", "passed": core_ops <= 30, "details": {"operations": core_ops}},
        {"name": "core_schema_server_correct", "passed": EXPECTED_SERVER in core, "details": {"expected_server": EXPECTED_SERVER}},
        {"name": "core_schema_auth_correct", "passed": "ApiKeyAuth:" in core and "x-api-key" in core and "- ApiKeyAuth: []" in core, "details": {}},
        {"name": "smoke_test_endpoint_in_schema", "passed": "/agent/coding-task/smoke-test:" in core, "details": {}},
        {"name": "instructions_under_8000_chars", "passed": len(instructions) < 8000, "details": {"chars": len(instructions)}},
        {"name": "instructions_under_8000_bytes", "passed": len(instructions.encode("utf-8")) < 8000, "details": {"bytes": len(instructions.encode("utf-8"))}},
        {"name": "knowledge_files_present", "passed": not knowledge_missing, "details": {"missing": knowledge_missing}},
        {"name": "phase_docs_present", "passed": not docs_missing, "details": {"missing": docs_missing}},
    ]
    if require_clean_git:
        checks.append({"name": "git_worktree_clean", "passed": git_state["clean"], "details": {"status_short": git_state["status_short"]}})
        checks.append({"name": "git_remote_matches_head", "passed": git_state["remote_matches_head"], "details": {"head": git_state["head"], "remote_hash": git_state["remote_hash"]}})
    passed = sum(1 for c in checks if c["passed"])
    return {
        "status": 200 if passed == len(checks) else 400,
        "version": PHASE13_VERSION,
        "total": len(checks),
        "passed": passed,
        "failed": len(checks) - passed,
        "checks": checks,
        "git": git_state,
    }


def _phase13_root() -> Path:
    root = eval_telemetry.eval_root() / "phase13"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _baselines_root() -> Path:
    root = eval_telemetry.eval_root() / "baselines"
    root.mkdir(parents=True, exist_ok=True)
    return root


def promote_baseline(report_id: str, *, run_id: str | None = None, reason: str = "phase13 promotion") -> dict[str, Any]:
    report_path = eval_telemetry.eval_root() / "reports" / f"{report_id}.json"
    if not report_path.exists():
        return {"status": 404, "error": {"code": "report_not_found", "message": f"Report not found: {report_id}"}}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    scores = report.get("scores", {})
    summary = report.get("summary", {})
    baseline = {
        "status": 200,
        "baseline_id": report_id,
        "promoted_at": int(time.time() * 1000),
        "promoted_by": PHASE13_VERSION,
        "run_id": run_id,
        "reason": reason,
        "summary": summary,
        "agent_score": (scores.get("agent") or {}).get("score"),
        "backend_score": (scores.get("backend") or {}).get("score"),
        "failure_count": len(report.get("failures", [])),
        "report_json": str(report_path),
        "report_md": summary.get("report_md"),
    }
    out = _baselines_root() / "latest_approved_baseline.json"
    history = _baselines_root() / f"baseline_{report_id}.json"
    out.write_text(json.dumps(baseline, indent=2, sort_keys=True), encoding="utf-8")
    history.write_text(json.dumps(baseline, indent=2, sort_keys=True), encoding="utf-8")
    eval_telemetry.log_event("phase13_baseline_promoted", run_id=run_id, report_id=report_id, baseline_path=str(out), version=PHASE13_VERSION)
    return {"status": 200, "baseline": baseline, "baseline_json": str(out), "history_json": str(history)}


def create_release_bundle(
    *,
    run_id: str,
    current_report_id: str | None = None,
    continuous_learning_md: str | None = None,
    release_gate_md: str | None = None,
    include_runtime_reports: bool = True,
) -> dict[str, Any]:
    root = _phase13_root()
    bundle_dir = root / f"bundle_{run_id}"
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True)
    manifest: dict[str, Any] = {
        "bundle_version": PHASE13_VERSION,
        "run_id": run_id,
        "created_at": int(time.time() * 1000),
        "git": _git_state(),
        "static_artifacts": [],
        "runtime_artifacts": [],
    }
    for rel in STATIC_ARTIFACTS:
        src = REPO_ROOT / rel
        if src.exists():
            dst = bundle_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            manifest["static_artifacts"].append(rel)
    runtime_paths = []
    if current_report_id:
        runtime_paths.extend([
            eval_telemetry.eval_root() / "reports" / f"{current_report_id}.json",
            eval_telemetry.eval_root() / "reports" / f"{current_report_id}.md",
        ])
    if continuous_learning_md:
        runtime_paths.append(Path(continuous_learning_md))
        runtime_paths.append(Path(str(continuous_learning_md).replace(".md", ".json")))
    if release_gate_md:
        runtime_paths.append(Path(release_gate_md))
        runtime_paths.append(Path(str(release_gate_md).replace(".md", ".json")))
    if include_runtime_reports:
        for src in runtime_paths:
            if src.exists():
                dst = bundle_dir / "runtime" / src.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                manifest["runtime_artifacts"].append(str(dst.relative_to(bundle_dir)))
    manifest_path = bundle_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    archive_path = root / f"phase13_release_bundle_{run_id}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(bundle_dir, arcname=bundle_dir.name)
    eval_telemetry.log_event("phase13_release_bundle_created", run_id=run_id, bundle_path=str(archive_path), version=PHASE13_VERSION)
    return {"status": 200, "bundle_dir": str(bundle_dir), "bundle_archive": str(archive_path), "manifest": manifest}


def _write_ops_report(result: dict[str, Any]) -> tuple[Path, Path]:
    root = _phase13_root()
    json_path = root / f"{result['run_id']}.json"
    md_path = root / f"{result['run_id']}.md"
    decision = result.get("ship_decision", {})
    readiness = result.get("readiness", {})
    baseline = result.get("baseline_promotion") or {}
    bundle = result.get("release_bundle") or {}
    lines = [
        f"# Coding GPT Phase 13 Production Ops: {result['run_id']}",
        "",
        "## Decision",
        "",
        f"- Complete: **{result.get('phase13_complete')}**",
        f"- Ship ready: **{decision.get('ship_ready')}**",
        f"- Blockers: `{', '.join(decision.get('blockers') or []) or 'none'}`",
        f"- Warnings: `{', '.join(decision.get('warnings') or []) or 'none'}`",
        "",
        "## Readiness",
        "",
        f"- Status: `{readiness.get('status')}`",
        f"- Passed: `{readiness.get('passed')}/{readiness.get('total')}`",
        "",
        "## Continuous learning",
        "",
        f"- Current report: `{result.get('current_report_id')}`",
        f"- Baseline report: `{result.get('baseline_report_id')}`",
        f"- Continuous learning report: `{result.get('continuous_learning_md')}`",
        "",
        "## Baseline and bundle",
        "",
        f"- Baseline promotion: `{baseline.get('status')}`",
        f"- Baseline JSON: `{baseline.get('baseline_json')}`",
        f"- Bundle archive: `{bundle.get('bundle_archive')}`",
        "",
        "## Phase 13 guarantees",
        "",
        "- Runs the complete continuous-learning release gate.",
        "- Verifies operational readiness.",
        "- Optionally promotes a passing run as runtime baseline.",
        "- Produces a portable release/evaluation artifact bundle.",
        "- Emits a clear ship/no-ship decision.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    result["phase13_json"] = str(json_path)
    result["phase13_md"] = str(md_path)
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return json_path, md_path


def run_phase13_production_ops(
    repo_path: str = DEFAULT_REPO,
    *,
    run_id: str | None = None,
    baseline_report_id: str | None = None,
    promote: bool = False,
    create_bundle: bool = True,
    require_clean_git: bool = True,
) -> dict[str, Any]:
    run_id = run_id or f"phase13_{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time() * 1000) % 10000:04d}"
    eval_telemetry.log_event("phase13_started", run_id=run_id, repo_path=repo_path, version=PHASE13_VERSION)
    baseline_report_id = baseline_report_id or _latest_report_id()
    cycle = run_continuous_learning_cycle(
        repo_path,
        run_id=f"{run_id}_continuous_learning",
        baseline_report_id=baseline_report_id,
        require_clean_git=require_clean_git,
    )
    readiness = operational_readiness(require_clean_git=require_clean_git)
    decision = dict(cycle.get("ship_decision") or {})
    blockers = list(decision.get("blockers") or [])
    if readiness.get("status") != 200:
        blockers.append("operational_readiness_failed")
    decision["blockers"] = sorted(set(blockers))
    decision["ship_ready"] = not decision["blockers"]
    current_report_id = cycle.get("current_report_id")
    baseline_promotion = None
    if promote:
        if decision["ship_ready"] and current_report_id:
            baseline_promotion = promote_baseline(current_report_id, run_id=run_id, reason="Phase 13 ship-ready promotion")
        else:
            baseline_promotion = {"status": 400, "error": {"code": "not_ship_ready", "message": "Baseline promotion skipped because Phase 13 decision is not ship-ready."}}
    release_bundle = None
    if create_bundle:
        release_bundle = create_release_bundle(
            run_id=run_id,
            current_report_id=current_report_id,
            continuous_learning_md=cycle.get("continuous_learning_md"),
            release_gate_md=(cycle.get("release_gate") or {}).get("release_gate_md"),
        )
    result = {
        "status": 200 if decision["ship_ready"] else 400,
        "phase13_complete": True,
        "version": PHASE13_VERSION,
        "run_id": run_id,
        "repo_path": repo_path,
        "baseline_report_id": baseline_report_id,
        "current_report_id": current_report_id,
        "continuous_learning": cycle,
        "continuous_learning_md": cycle.get("continuous_learning_md"),
        "readiness": readiness,
        "ship_decision": decision,
        "baseline_promotion": baseline_promotion,
        "release_bundle": release_bundle,
    }
    _write_ops_report(result)
    eval_telemetry.log_event("phase13_completed", run_id=run_id, repo_path=repo_path, status=result["status"], ship_ready=decision["ship_ready"], blockers=decision.get("blockers"), version=PHASE13_VERSION)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Coding GPT Phase 13 production operations cycle")
    parser.add_argument("--repo-path", default=DEFAULT_REPO)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--baseline-report-id", default=None)
    parser.add_argument("--promote", action="store_true")
    parser.add_argument("--no-bundle", action="store_true")
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args(argv)
    result = run_phase13_production_ops(
        args.repo_path,
        run_id=args.run_id,
        baseline_report_id=args.baseline_report_id,
        promote=args.promote,
        create_bundle=not args.no_bundle,
        require_clean_git=not args.allow_dirty,
    )
    print(json.dumps({
        "status": result["status"],
        "phase13_complete": result["phase13_complete"],
        "run_id": result["run_id"],
        "ship_ready": result["ship_decision"]["ship_ready"],
        "blockers": result["ship_decision"].get("blockers"),
        "current_report_id": result.get("current_report_id"),
        "phase13_json": result.get("phase13_json"),
        "phase13_md": result.get("phase13_md"),
        "bundle_archive": (result.get("release_bundle") or {}).get("bundle_archive"),
        "baseline_json": (result.get("baseline_promotion") or {}).get("baseline_json"),
    }, indent=2))
    return 0 if result["status"] == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
