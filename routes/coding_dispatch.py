from __future__ import annotations

import time
from typing import Any, Callable

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from utils.auth import verify_key
from utils.policy import PolicyError, policy_result_for_path, evaluate_action, evaluate_action_deep
from utils import (
    repo_intel, worktrees, patching, test_discovery, task_ledger,
    github_safe, diagnostics, env_tools,
)
from utils.safe_subprocess import run_checked

router = APIRouter(dependencies=[Depends(verify_key)])


class CategoryActionRequest(BaseModel):
    action: str = Field(..., description="Allowlisted action name for this category.")
    payload: dict[str, Any] = Field(default_factory=dict, description="Action-specific payload.")


class CodingActionRequest(CategoryActionRequest):
    category: str = Field(..., description="Allowlisted category: repo, workspace, patch, test, quality, diagnostics, policy, tasks, github, env.")


def _ok(out: Any, start: float) -> dict[str, Any]:
    if isinstance(out, dict):
        result = out
    else:
        result = {"result": out}
    result.setdefault("status", 200)
    result["latency_ms"] = round((time.time() - start) * 1000, 2)
    result["timestamp"] = int(time.time() * 1000)
    return result


def _err(code: str, message: str, status: int = 400) -> dict[str, Any]:
    return {"status": status, "error": {"code": code, "message": message}}


def _required(payload: dict[str, Any], *names: str) -> list[Any]:
    missing = [n for n in names if n not in payload or payload[n] is None]
    if missing:
        raise PolicyError("missing_payload_fields", f"Missing required payload fields: {', '.join(missing)}")
    return [payload[n] for n in names]


def _dispatch(action_map: dict[str, Callable[[dict[str, Any]], Any]], req: CategoryActionRequest) -> dict[str, Any]:
    start = time.time()
    try:
        action = (req.action or "").strip().replace("-", "_")
        fn = action_map.get(action)
        if not fn:
            return _err("unsupported_action", f"Unsupported action: {req.action}. Allowed actions: {', '.join(sorted(action_map))}")
        return _ok(fn(req.payload or {}), start)
    except PolicyError as exc:
        return _err(exc.code, exc.message)
    except Exception as exc:
        return _err("internal_error", str(exc), 500)


def _repo_actions() -> dict[str, Callable[[dict[str, Any]], Any]]:
    return {
        "overview": lambda p: repo_intel.overview(*_required(p, "repo_path"), p.get("max_depth", 4)),
        "search": lambda p: repo_intel.search(*_required(p, "repo_path", "query"), p.get("globs"), p.get("max_results", 50)),
        "read_context": lambda p: repo_intel.read_context(*_required(p, "repo_path", "files"), p.get("max_bytes_per_file", 50000)),
        "symbols": lambda p: repo_intel.symbols(*_required(p, "repo_path"), p.get("files")),
        "instructions": lambda p: repo_intel.repo_instructions(*_required(p, "repo_path")),
        "dependency_graph": lambda p: repo_intel.dependency_graph(*_required(p, "repo_path")),
        "test_map": lambda p: repo_intel.test_map(*_required(p, "repo_path")),
        "relevant_context": lambda p: repo_intel.relevant_context(*_required(p, "repo_path", "task"), p.get("diagnostics"), p.get("max_files", 12)),
        "callgraph": lambda p: repo_intel.callgraph(*_required(p, "repo_path"), p.get("max_files", 500)),
        "references": lambda p: repo_intel.references(*_required(p, "repo_path", "symbol"), p.get("max_results", 100)),
        "symbol_references": lambda p: repo_intel.symbol_references(*_required(p, "repo_path", "symbols"), p.get("max_results_per_symbol", 50)),
        "route_map": lambda p: repo_intel.route_map(*_required(p, "repo_path")),
        "changed_context": lambda p: repo_intel.changed_context(*_required(p, "repo_path"), p.get("base_ref")),
        "recent_history_context": lambda p: repo_intel.recent_history_context(*_required(p, "repo_path"), p.get("query"), p.get("max_commits", 20)),
    }


def _workspace_actions() -> dict[str, Callable[[dict[str, Any]], Any]]:
    return {
        "create": lambda p: worktrees.create_worktree(*_required(p, "repo_path", "task_id"), p.get("base_branch")),
        "status": lambda p: worktrees.status(*_required(p, "workspace_path")),
        "diff": lambda p: worktrees.diff(*_required(p, "workspace_path"), p.get("staged", False)),
        "destroy": lambda p: worktrees.destroy(*_required(p, "workspace_path"), p.get("force", False), p.get("keep_branch", True)),
        "commit": lambda p: worktrees.commit(*_required(p, "workspace_path", "message"), p.get("files")),
        "pr_create": lambda p: worktrees.pr_create(*_required(p, "workspace_path", "title"), p.get("body", ""), p.get("dry_run", True)),
        "diff_summary": lambda p: worktrees.diff_summary(*_required(p, "workspace_path")),
        "risk_report": lambda p: worktrees.risk_report(*_required(p, "workspace_path")),
        "review_checklist": lambda p: worktrees.review_checklist(*_required(p, "workspace_path")),
    }


def _patch_actions() -> dict[str, Callable[[dict[str, Any]], Any]]:
    return {
        "preview": lambda p: patching.preview(*_required(p, "workspace_path", "patch")),
        "apply": lambda p: patching.apply_patch(*_required(p, "workspace_path", "patch")),
        "revert": lambda p: patching.revert_patch(*_required(p, "workspace_path", "patch")),
        "apply_recorded": lambda p: patching.apply_recorded(*_required(p, "workspace_path", "patch"), p.get("task_id"), p.get("label")),
        "history": lambda p: patching.history(*_required(p, "workspace_path"), p.get("task_id")),
        "revert_recorded": lambda p: patching.revert_recorded(*_required(p, "workspace_path", "patch_id")),
        "validate_risk": lambda p: patching.validate_risk(*_required(p, "workspace_path", "patch"), p.get("max_files", 25), p.get("max_lines", 2000)),
    }


def _test_actions() -> dict[str, Callable[[dict[str, Any]], Any]]:
    return {
        "discover": lambda p: test_discovery.discover(*_required(p, "workspace_path")),
        "run": lambda p: test_discovery.run_discovered(*_required(p, "workspace_path", "command_name"), p.get("timeout_seconds", 120)),
    }


def _quality_actions() -> dict[str, Callable[[dict[str, Any]], Any]]:
    def check(p: dict[str, Any]) -> dict[str, Any]:
        workspace_path, = _required(p, "workspace_path")
        results = []
        for cmd in test_discovery.quality_commands(workspace_path):
            result = run_checked(cmd["argv"], workspace_path, timeout=p.get("timeout_seconds", 120))
            results.append({"name": cmd["name"], "argv": cmd["argv"], "passed": result["passed"], "exit_code": result["exit_code"], "stdout_tail": result["stdout"][-4000:], "stderr_tail": result["stderr"][-4000:]})
        return {"passed": all(r["passed"] for r in results), "results": results}
    return {"check": check}


def _diagnostics_actions() -> dict[str, Callable[[dict[str, Any]], Any]]:
    return {
        "parse": lambda p: diagnostics.parse(*_required(p, "tool"), p.get("stdout", ""), p.get("stderr", "")),
        "suggest_context": lambda p: diagnostics.suggest_context(*_required(p, "diagnostics"), p.get("max_files", 20)),
        "triage": lambda p: diagnostics.triage(*_required(p, "diagnostics"), p.get("task"), p.get("max_files", 20)),
    }


def _policy_actions() -> dict[str, Callable[[dict[str, Any]], Any]]:
    return {
        "check": lambda p: policy_result_for_path(*_required(p, "path"), p.get("repo_root")),
        "evaluate_action": lambda p: evaluate_action(*_required(p, "action"), p.get("workspace_path"), p.get("changed_files"), p.get("tests_passed"), p.get("quality_passed"), p.get("user_approved_network_write", False)),
        "evaluate_action_deep": lambda p: evaluate_action_deep(*_required(p, "action"), p.get("workspace_path"), p.get("changed_files"), p.get("tests_passed"), p.get("quality_passed"), p.get("user_approved_network_write", False), p.get("user_approved_sensitive", False), p.get("user_approved_large_diff", False), p.get("user_approved_deletions", False), p.get("diff_line_count", 0)),
    }


def _tasks_actions() -> dict[str, Callable[[dict[str, Any]], Any]]:
    return {
        "create": lambda p: task_ledger.create(*_required(p, "task", "repo_path"), p.get("workspace_path"), p.get("metadata")),
        "update": lambda p: task_ledger.update(*_required(p, "task_id"), p.get("status"), p.get("workspace_path"), p.get("metadata")),
        "read": lambda p: task_ledger.read(*_required(p, "task_id")),
        "list": lambda p: task_ledger.list_tasks(p.get("status")),
        "cancel": lambda p: task_ledger.cancel(*_required(p, "task_id"), p.get("reason")),
        "lock": lambda p: task_ledger.lock(*_required(p, "task_id"), p.get("owner", "coding-gpt")),
        "claim": lambda p: task_ledger.claim(*_required(p, "task_id"), p.get("owner", "coding-gpt")),
        "unlock": lambda p: task_ledger.unlock(*_required(p, "task_id"), p.get("owner", "coding-gpt")),
        "log": lambda p: task_ledger.log_event(*_required(p, "task_id", "event_type"), p.get("data")),
        "artifacts": lambda p: task_ledger.add_artifact(*_required(p, "task_id", "name", "artifact")),
        "resume": lambda p: task_ledger.resume(*_required(p, "task_id")),
        "status_summary": lambda p: task_ledger.status_summary(),
        "gc": lambda p: task_ledger.gc(p.get("max_age_ms", 604800000), p.get("statuses"), p.get("dry_run", True)),
        "lock_ttl": lambda p: task_ledger.lock_ttl(*_required(p, "task_id"), p.get("owner", "coding-gpt"), p.get("ttl_ms", 1800000)),
        "artifact_index": lambda p: task_ledger.artifact_index(*_required(p, "task_id")),
        "validate_artifacts": lambda p: task_ledger.validate_required_artifacts(*_required(p, "task_id"), p.get("required")),
        "phase_contract": lambda p: task_ledger.phase_contract(*_required(p, "task_id")),
        "iteration_summary": lambda p: task_ledger.iteration_summary(*_required(p, "task_id")),
    }


def _github_actions() -> dict[str, Callable[[dict[str, Any]], Any]]:
    def pr_create_from_task(p: dict[str, Any]) -> dict[str, Any]:
        workspace_path, task_id = _required(p, "workspace_path", "task_id")
        return github_safe.pr_create_from_task(workspace_path, task_ledger.read(task_id), p.get("title"), p.get("dry_run", True))
    return {
        "issue_read": lambda p: github_safe.issue_read(*_required(p, "workspace_path", "issue")),
        "pr_read": lambda p: github_safe.pr_read(*_required(p, "workspace_path", "pr")),
        "checks_read": lambda p: github_safe.checks_read(*_required(p, "workspace_path"), p.get("ref")),
        "pr_comment": lambda p: github_safe.pr_comment(*_required(p, "workspace_path", "pr", "body"), p.get("dry_run", True)),
        "pr_create_from_task": pr_create_from_task,
        "checks_diagnose": lambda p: github_safe.checks_diagnose(*_required(p, "checks")),
        "pr_apply_feedback_plan": lambda p: github_safe.apply_feedback_plan(*_required(p, "workspace_path", "comments")),
        "pr_update_body": lambda p: github_safe.pr_update_body(*_required(p, "workspace_path", "pr", "body"), p.get("dry_run", True)),
        "pr_review_comments": lambda p: github_safe.review_comments(*_required(p, "workspace_path", "pr")),
        "checks_logs": lambda p: github_safe.checks_logs(*_required(p, "workspace_path"), p.get("ref"), p.get("dry_run", True)),
        "branch_push": lambda p: github_safe.branch_push(*_required(p, "workspace_path"), p.get("remote", "origin"), p.get("branch"), p.get("dry_run", True)),
        "checks_repair_plan": lambda p: github_safe.ci_repair_plan(*_required(p, "workspace_path"), p.get("checks"), p.get("logs")),
        "pr_feedback_to_patch_contract": lambda p: github_safe.feedback_to_patch_contract(*_required(p, "workspace_path", "comments")),
    }


def _env_actions() -> dict[str, Callable[[dict[str, Any]], Any]]:
    return {
        "discover": lambda p: env_tools.discover(*_required(p, "workspace_path")),
        "doctor": lambda p: env_tools.doctor(*_required(p, "workspace_path")),
        "prepare_dry_run": lambda p: env_tools.prepare_plan(*_required(p, "workspace_path")),
        "prepare_approved": lambda p: env_tools.prepare_approved(*_required(p, "workspace_path"), p.get("approved", False)),
    }


CATEGORY_MAP = {
    "repo": _repo_actions,
    "workspace": _workspace_actions,
    "patch": _patch_actions,
    "test": _test_actions,
    "quality": _quality_actions,
    "diagnostics": _diagnostics_actions,
    "policy": _policy_actions,
    "tasks": _tasks_actions,
    "github": _github_actions,
    "env": _env_actions,
}


@router.post("/action")
def coding_action(req: CodingActionRequest):
    category = (req.category or "").strip().replace("-", "_")
    factory = CATEGORY_MAP.get(category)
    if not factory:
        return _err("unsupported_category", f"Unsupported category: {req.category}. Allowed categories: {', '.join(sorted(CATEGORY_MAP))}")
    return _dispatch(factory(), CategoryActionRequest(action=req.action, payload=req.payload))


@router.post("/repo/action")
def repo_action(req: CategoryActionRequest): return _dispatch(_repo_actions(), req)

@router.post("/workspace/action")
def workspace_action(req: CategoryActionRequest): return _dispatch(_workspace_actions(), req)

@router.post("/patch/action")
def patch_action(req: CategoryActionRequest): return _dispatch(_patch_actions(), req)

@router.post("/test/action")
def test_action(req: CategoryActionRequest): return _dispatch(_test_actions(), req)

@router.post("/quality/action")
def quality_action(req: CategoryActionRequest): return _dispatch(_quality_actions(), req)

@router.post("/diagnostics/action")
def diagnostics_action(req: CategoryActionRequest): return _dispatch(_diagnostics_actions(), req)

@router.post("/policy/action")
def policy_action(req: CategoryActionRequest): return _dispatch(_policy_actions(), req)

@router.post("/tasks/action")
def tasks_action(req: CategoryActionRequest): return _dispatch(_tasks_actions(), req)

@router.post("/github/action")
def github_action(req: CategoryActionRequest): return _dispatch(_github_actions(), req)

@router.post("/env/action")
def env_action(req: CategoryActionRequest): return _dispatch(_env_actions(), req)
