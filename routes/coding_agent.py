from __future__ import annotations

import re
import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from utils.auth import verify_key
from utils.policy import PolicyError
from utils import repo_intel, worktrees, test_discovery, task_ledger, eval_telemetry

router = APIRouter(dependencies=[Depends(verify_key)])


class CodingTaskRequest(BaseModel):
    repo_path: str
    task: str
    mode: str = "plan_apply_verify"
    workspace_strategy: str = "git_worktree"
    max_iterations: int = 5
    approval_policy: str = "safe_auto"
    create_pr: bool = False
    base_branch: str | None = None
    task_id: str | None = None
    compact_response: bool = True


def _slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", text.lower()).strip("-")[:60] or "coding-task"


@router.post("/coding-task")
def coding_task(req: CodingTaskRequest):
    start = time.time()
    eval_telemetry.log_event("task_started", endpoint="/agent/coding-task", repo_path=req.repo_path, task_preview=req.task[:200], mode=req.mode, workspace_strategy=req.workspace_strategy, approval_policy=req.approval_policy, create_pr=req.create_pr)
    try:
        if req.mode != "plan_apply_verify":
            return {"error": {"code": "unsupported_mode", "message": "Only plan_apply_verify is supported."}, "status": 400}
        if req.workspace_strategy != "git_worktree":
            return {"error": {"code": "unsupported_workspace_strategy", "message": "Only git_worktree is supported."}, "status": 400}
        if req.approval_policy not in {"safe_auto", "manual_network_writes", "dry_run_only"}:
            return {"error": {"code": "unsupported_approval_policy", "message": "Supported policies: safe_auto, manual_network_writes, dry_run_only."}, "status": 400}

        overview = repo_intel.overview(req.repo_path, 2 if req.compact_response else 4)
        ledger = task_ledger.read(req.task_id) if req.task_id else task_ledger.create(
            task=req.task,
            repo_path=req.repo_path,
            metadata={"mode": req.mode, "approval_policy": req.approval_policy, "create_pr": req.create_pr},
        )
        workspace = worktrees.create_worktree(req.repo_path, _slug(req.task), req.base_branch)
        ledger = task_ledger.update(ledger["task_id"], status="workspace_ready", workspace_path=workspace["workspace_path"])
        tests = test_discovery.discover(workspace["workspace_path"])
        plan = [
            "Inspect repository overview and current git state.",
            "Use the isolated worktree for all changes.",
            "Search and read focused context relevant to the task.",
            "Apply only policy-checked patches via /patch/preview and /patch/apply.",
            "Run discovered focused tests, then broader quality checks when available.",
            "Store diff/test/quality artifacts in the task ledger.",
            "Return final diff, tests run, risks, and next steps.",
        ]
        task_ledger.log_event(ledger["task_id"], "plan_created", {"plan": plan})
        task_record = task_ledger.read(ledger["task_id"])
        eval_telemetry.log_event("action_completed", endpoint="/agent/coding-task", task_id=ledger["task_id"], repo_path=req.repo_path, workspace_path=workspace.get("workspace_path"), status="workspace_ready", latency_ms=round((time.time() - start) * 1000, 2))
        compact_overview = {
            "repo_path": overview.get("repo_path"),
            "is_git_repo": overview.get("is_git_repo"),
            "branch": overview.get("branch"),
            "dirty": overview.get("dirty"),
            "languages": overview.get("languages", []),
            "frameworks": overview.get("frameworks", []),
            "important_files": overview.get("important_files", []),
            "test_commands": overview.get("test_commands", []),
            "quality_commands": overview.get("quality_commands", []),
        }
        return {
            "status": "workspace_ready",
            "message": "Coding task initialized safely. Store repo_path, task_id, and workspace_path. Then call /agent/coding-task/next before acting and generate a patch. For endpoint smoke tests, call /agent/coding-task/smoke-test.",
            "task": task_record if not req.compact_response else {"task_id": task_record.get("task_id"), "task": task_record.get("task"), "repo_path": task_record.get("repo_path"), "workspace_path": task_record.get("workspace_path"), "status": task_record.get("status"), "metadata": task_record.get("metadata", {})},
            "workspace": workspace,
            "overview": compact_overview if req.compact_response else overview,
            "test_discovery": tests,
            "plan": plan,
            "next_required_call": "/agent/coding-task/next",
            "dispatcher_payload_rule": "Never call /coding/*/action with only action. Always include payload with required repo_path, workspace_path, task_id, or other required fields.",
            "max_iterations": min(max(req.max_iterations, 1), 10),
            "create_pr": req.create_pr,
            "approval_policy": req.approval_policy,
            "latency_ms": round((time.time() - start) * 1000, 2),
            "timestamp": int(time.time() * 1000),
        }
    except PolicyError as exc:
        eval_telemetry.log_error("action_failed", exc, endpoint="/agent/coding-task", repo_path=req.repo_path, status=400, latency_ms=round((time.time() - start) * 1000, 2))
        return {"error": {"code": exc.code, "message": exc.message}, "status": 400}
    except Exception as exc:
        eval_telemetry.log_error("action_failed", exc, endpoint="/agent/coding-task", repo_path=req.repo_path, status=500, latency_ms=round((time.time() - start) * 1000, 2))
        return {"error": {"code": "internal_error", "message": str(exc)}, "status": 500}


class CodingTaskNextRequest(BaseModel):
    task_id: str


@router.post("/coding-task/next")
def coding_task_next(req: CodingTaskNextRequest):
    start = time.time()
    eval_telemetry.log_event("action_called", endpoint="/agent/coding-task/next", task_id=req.task_id)
    try:
        task = task_ledger.read(req.task_id)
        status = task.get("status")
        workspace_path = task.get("workspace_path")
        artifacts = task.get("artifacts", {})
        if not workspace_path:
            phase = "need_workspace"
            required_action = {"endpoint": "/workspace/create", "then": "/tasks/update"}
        elif "relevant_context" not in artifacts:
            phase = "need_context"
            required_action = {"endpoint": "/repo/relevant-context", "then": "/tasks/artifacts"}
        elif "coverage_baseline" not in artifacts and ("coverage" in task.get("task","").lower() or "test" in task.get("task","").lower()):
            phase = "need_baseline"
            required_action = {"endpoint": "/test/discover then /test/run coverage command", "then": "/tasks/artifacts coverage_baseline"}
        elif "patch_preview" not in artifacts:
            phase = "need_patch"
            required_action = {"format": "unified_diff", "endpoint": "/patch/preview", "then": "/patch/apply"}
        elif "test_result" not in artifacts:
            phase = "need_tests"
            required_action = {"endpoint": "/test/discover then /test/run", "then": "/tasks/artifacts"}
        elif "quality_result" not in artifacts:
            phase = "need_quality"
            required_action = {"endpoint": "/quality/check", "then": "/tasks/artifacts"}
        elif "diff_summary" not in artifacts:
            phase = "need_review"
            required_action = {"endpoint": "/workspace/diff-summary and /workspace/review-checklist", "then": "/tasks/artifacts"}
        else:
            phase = "ready_to_finalize"
            required_action = {"endpoint": "/policy/evaluate-action", "next": "commit or PR dry-run if policy allows"}
        contract = task_ledger.phase_contract(req.task_id)
        task_ledger.log_event(req.task_id, "next_phase", {"phase": contract.get("phase")})
        latency = round((time.time() - start) * 1000, 2)
        eval_telemetry.log_event("task_phase_selected", endpoint="/agent/coding-task/next", task_id=req.task_id, phase=contract.get("phase"), status=200, latency_ms=latency)
        return {"status": 200, "phase": contract.get("phase"), "required_action": required_action, "contract": contract.get("contract"), "validation": contract.get("validation"), "task": task_ledger.read(req.task_id), "latency_ms": latency, "timestamp": int(time.time() * 1000)}
    except PolicyError as exc:
        return {"status": 400, "error": {"code": exc.code, "message": exc.message}}
    except Exception as exc:
        return {"status": 500, "error": {"code": "internal_error", "message": str(exc)}}


class CodingTaskSubmitRequest(BaseModel):
    task_id: str
    artifact_name: str | None = None
    artifact: dict | None = None
    patch: str | None = None
    run_tests: bool = False
    run_quality: bool = False

class CodingTaskFinalizeRequest(BaseModel):
    task_id: str
    commit: bool = False
    commit_message: str | None = None
    create_pr: bool = False
    pr_title: str | None = None
    pr_body: str = ""
    user_approved_network_write: bool = False
    enforce_contract: bool = True


@router.post("/coding-task/submit")
def coding_task_submit(req: CodingTaskSubmitRequest):
    start = time.time()
    eval_telemetry.log_event("action_called", endpoint="/agent/coding-task/submit", task_id=req.task_id, artifact_name=req.artifact_name, has_patch=bool(req.patch), run_tests=req.run_tests, run_quality=req.run_quality)
    try:
        from utils import patching
        from utils import diagnostics as diagnostics_util
        from utils import policy as policy_util
        task = task_ledger.read(req.task_id)
        workspace = task.get("workspace_path")
        if not workspace:
            raise PolicyError("workspace_missing", "Task has no workspace path.")
        results = {}
        if req.artifact_name and req.artifact is not None:
            task_ledger.add_artifact(req.task_id, req.artifact_name, req.artifact)
            eval_telemetry.log_event("artifact_recorded", endpoint="/agent/coding-task/submit", task_id=req.task_id, artifact_name=req.artifact_name)
            results[req.artifact_name] = req.artifact
        if req.patch:
            current_task = task_ledger.read(req.task_id)
            current_artifacts = current_task.get("artifacts", {})
            if task_ledger.is_coverage_task(current_task) and patching.touches_coverage_threshold(req.patch):
                missing_cov = [name for name in ["coverage_baseline", "coverage_report", "coverage_gaps"] if name not in current_artifacts]
                if missing_cov:
                    task_ledger.update(req.task_id, status="blocked_coverage_baseline_required")
                    return {"status": 400, "error": {"code": "coverage_baseline_required", "message": "Coverage threshold/config patches require measured baseline and gap artifacts first."}, "missing": missing_cov, "required_artifacts": ["coverage_baseline", "coverage_report", "coverage_gaps"]}
            risk = patching.validate_risk(workspace, req.patch)
            eval_telemetry.log_event("patch_previewed", endpoint="/agent/coding-task/submit", task_id=req.task_id, workspace_path=workspace, allowed=risk.get("allowed"), files_touched=risk.get("files_touched"), risk_count=len(risk.get("risks", [])))
            task_ledger.add_artifact(req.task_id, "patch_risk", risk)
            if not risk.get("allowed"):
                task_ledger.update(req.task_id, status="blocked_patch_risk")
                err_code = "invalid_unified_diff" if risk.get("diagnostics") else "patch_risk_blocked"
                return {"status": 400, "error": {"code": err_code, "message": "Patch failed risk validation."}, "risk": risk, "diagnostics": risk.get("diagnostics")}
            preview = patching.preview(workspace, req.patch)
            task_ledger.add_artifact(req.task_id, "patch_preview", preview)
            if not preview.get("applies"):
                task_ledger.update(req.task_id, status="patch_preview_failed")
                return {"status": 400, "error": {"code": "patch_preview_failed", "message": preview.get("stderr") or preview.get("preview")}, "preview": preview}
            applied = patching.apply_recorded(workspace, req.patch, req.task_id, "agent_submit")
            eval_telemetry.log_event("patch_applied", endpoint="/agent/coding-task/submit", task_id=req.task_id, workspace_path=workspace, patch_id=applied.get("patch_id"), applied=applied.get("applied"), files_touched=applied.get("files_touched"))
            task_ledger.add_artifact(req.task_id, "patch_recorded", applied)
            task_ledger.update(req.task_id, status="patch_applied")
            results["patch"] = {"patch_id": applied.get("patch_id"), "applied": applied.get("applied"), "files_touched": applied.get("files_touched")}
        if req.run_tests:
            tests = test_discovery.discover(workspace)
            task_ledger.add_artifact(req.task_id, "test_discovery", tests)
            eval_telemetry.log_event("tests_discovered", endpoint="/agent/coding-task/submit", task_id=req.task_id, workspace_path=workspace, command_count=len(tests.get("commands", [])), frameworks=tests.get("frameworks"))
            command = (tests.get("commands") or [{}])[0].get("name") if tests.get("commands") else None
            if command:
                test_result = test_discovery.run_discovered(workspace, command)
            else:
                test_result = {"passed": False, "error": {"code": "no_test_command", "message": "No discovered test command."}}
            task_ledger.add_artifact(req.task_id, "test_result", test_result)
            eval_telemetry.log_event("tests_run", endpoint="/agent/coding-task/submit", task_id=req.task_id, workspace_path=workspace, passed=test_result.get("passed"), exit_code=test_result.get("exit_code"), command_name=test_result.get("command_name"))
            results["tests"] = test_result
            if not test_result.get("passed"):
                parsed = diagnostics_util.parse("pytest", test_result.get("stdout_tail", ""), test_result.get("stderr_tail", ""))
                task_ledger.add_artifact(req.task_id, "diagnostics", parsed)
                task_ledger.update(req.task_id, status="tests_failed")
        if req.run_quality:
            from utils import test_discovery as td
            quality_results = []
            for cmd in td.quality_commands(workspace):
                from utils.safe_subprocess import run_checked
                result = run_checked(cmd["argv"], workspace, timeout=120)
                quality_results.append({"command": cmd.get("name"), "argv": cmd["argv"], **result})
            quality_result = {"passed": all(r.get("passed") for r in quality_results), "results": quality_results}
            task_ledger.add_artifact(req.task_id, "quality_result", quality_result)
            eval_telemetry.log_event("quality_run", endpoint="/agent/coding-task/submit", task_id=req.task_id, workspace_path=workspace, passed=quality_result.get("passed"), result_count=len(quality_result.get("results", [])))
            results["quality"] = quality_result
        # auto-generate review artifacts when enough data exists
        try:
            task_ledger.add_artifact(req.task_id, "diff_summary", worktrees.diff_summary(workspace))
            task_ledger.add_artifact(req.task_id, "risk_report", worktrees.risk_report(workspace))
            task_ledger.add_artifact(req.task_id, "review_checklist", worktrees.review_checklist(workspace))
        except Exception:
            pass
        if req.run_quality and 'quality_result' in locals() and not quality_result.get("passed"):
            task_ledger.update(req.task_id, status="quality_failed")
        latency = round((time.time()-start)*1000,2)
        eval_telemetry.log_event("action_completed", endpoint="/agent/coding-task/submit", task_id=req.task_id, status=200, result_keys=sorted(results.keys()), latency_ms=latency)
        return {"status": 200, "results": results, "task": task_ledger.read(req.task_id), "latency_ms": latency, "timestamp": int(time.time()*1000)}
    except PolicyError as exc:
        return {"status": 400, "error": {"code": exc.code, "message": exc.message}}
    except Exception as exc:
        return {"status": 500, "error": {"code": "internal_error", "message": str(exc)}}


@router.post("/coding-task/finalize")
def coding_task_finalize(req: CodingTaskFinalizeRequest):
    start = time.time()
    eval_telemetry.log_event("action_called", endpoint="/agent/coding-task/finalize", task_id=req.task_id, commit=req.commit, create_pr=req.create_pr)
    try:
        from utils import policy as policy_util
        task = task_ledger.read(req.task_id)
        workspace = task.get("workspace_path")
        if not workspace:
            raise PolicyError("workspace_missing", "Task has no workspace path.")
        diff_summary = worktrees.diff_summary(workspace)
        risk_report = worktrees.risk_report(workspace)
        review = worktrees.review_checklist(workspace)
        task_ledger.add_artifact(req.task_id, "diff_summary", diff_summary)
        task_ledger.add_artifact(req.task_id, "risk_report", risk_report)
        task_ledger.add_artifact(req.task_id, "review_checklist", review)
        tests = task.get("artifacts", {}).get("test_result", {}).get("data", {})
        quality = task.get("artifacts", {}).get("quality_result", {}).get("data", {})
        changed = [f.get("file") for f in diff_summary.get("files", []) if f.get("file")]
        validation_before_policy = task_ledger.validate_required_artifacts(req.task_id)
        if req.enforce_contract and not validation_before_policy.get("valid"):
            return {"status": 400, "error": {"code": "contract_incomplete", "message": "Required task artifacts are missing before finalization."}, "validation": validation_before_policy}
        diff_lines = sum(int(x.split("	")[0]) + int(x.split("	")[1]) for x in diff_summary.get("numstat", "").splitlines() if len(x.split("	")) >= 3 and x.split("	")[0].isdigit() and x.split("	")[1].isdigit())
        policy_result = policy_util.evaluate_action_deep(
            "create_pr" if (req.create_pr and req.user_approved_network_write) else "commit" if req.commit else "finalize",
            workspace,
            changed,
            tests.get("passed") if tests else None,
            quality.get("passed") if quality else None,
            req.user_approved_network_write,
            False,
            False,
            False,
            diff_lines,
        )
        task_ledger.add_artifact(req.task_id, "policy_result", policy_result)
        result = {"diff_summary": diff_summary, "risk_report": risk_report, "review_checklist": review, "policy_result": policy_result, "contract_validation": validation_before_policy}
        if req.commit:
            if not policy_result.get("allowed"):
                return {"status": 400, "error": {"code": "policy_blocked", "message": "Policy blocked commit/finalize."}, **result}
            commit_result = worktrees.commit(workspace, req.commit_message or f"Complete task {req.task_id}")
            task_ledger.add_artifact(req.task_id, "commit", commit_result)
            result["commit"] = commit_result
        if req.create_pr:
            pr_result = worktrees.pr_create(workspace, req.pr_title or task.get("task") or req.task_id, req.pr_body, dry_run=not req.user_approved_network_write)
            task_ledger.add_artifact(req.task_id, "pr", pr_result)
            result["pr"] = pr_result
        report = task_ledger.final_report(req.task_id)
        task_ledger.add_artifact(req.task_id, "final_report", report)
        task_ledger.update(req.task_id, status="finalized")
        latency = round((time.time()-start)*1000,2)
        eval_telemetry.log_event("task_finalized", endpoint="/agent/coding-task/finalize", task_id=req.task_id, status=200, commit=req.commit, create_pr=req.create_pr, policy_allowed=policy_result.get("allowed"), latency_ms=latency)
        return {"status": 200, "result": result, "final_report": report, "latency_ms": latency, "timestamp": int(time.time()*1000)}
    except PolicyError as exc:
        return {"status": 400, "error": {"code": exc.code, "message": exc.message}}
    except Exception as exc:
        return {"status": 500, "error": {"code": "internal_error", "message": str(exc)}}


class CodingTaskRepairPlanRequest(BaseModel):
    task_id: str
    max_files: int = 12

class CodingTaskContractReportRequest(BaseModel):
    task_id: str

@router.post("/coding-task/repair-plan")
def coding_task_repair_plan(req: CodingTaskRepairPlanRequest):
    start = time.time()
    eval_telemetry.log_event("action_called", endpoint="/agent/coding-task/repair-plan", task_id=req.task_id, max_files=req.max_files)
    try:
        from utils import diagnostics as diagnostics_util
        task = task_ledger.read(req.task_id)
        artifacts = task.get("artifacts", {})
        diagnostics_payload = artifacts.get("diagnostics", {}).get("data", {})
        diagnostics_list = diagnostics_payload.get("diagnostics", []) if isinstance(diagnostics_payload, dict) else []
        if not diagnostics_list:
            test_result = artifacts.get("test_result", {}).get("data", {})
            quality_result = artifacts.get("quality_result", {}).get("data", {})
            text = (test_result.get("stdout_tail", "") + "\n" + test_result.get("stderr_tail", "")) if isinstance(test_result, dict) else ""
            if not text and isinstance(quality_result, dict):
                text = "\n".join((r.get("stdout", "") + "\n" + r.get("stderr", "")) for r in quality_result.get("results", []) if isinstance(r, dict))
            parsed = diagnostics_util.parse("quality" if quality_result else "pytest", text, "")
            diagnostics_list = parsed.get("diagnostics", [])
            task_ledger.add_artifact(req.task_id, "diagnostics", parsed)
        triage = diagnostics_util.triage(diagnostics_list, task.get("task"), req.max_files)
        plan = {
            "task_id": req.task_id,
            "phase": task_ledger.phase_contract(req.task_id).get("phase"),
            "triage": triage,
            "required_gpt_behavior": [
                "Read only the next_context files before patching.",
                "Generate a minimal unified diff only.",
                "Do not broaden scope or touch unrelated files.",
                "Submit the repair patch through /agent/coding-task/submit with run_tests=true and run_quality=true when appropriate.",
            ],
            "recommended_context_files": triage.get("next_context", [])[:req.max_files],
            "repair_strategy": triage.get("repair_strategy"),
        }
        task_ledger.add_artifact(req.task_id, "repair_plan", plan)
        task_ledger.log_event(req.task_id, "repair_plan_created", {"phase": plan["phase"]})
        latency = round((time.time()-start)*1000,2)
        eval_telemetry.log_event("repair_plan_created", endpoint="/agent/coding-task/repair-plan", task_id=req.task_id, phase=plan.get("phase"), recommended_context_files=plan.get("recommended_context_files"), latency_ms=latency)
        return {"status": 200, "repair_plan": plan, "latency_ms": latency, "timestamp": int(time.time()*1000)}
    except PolicyError as exc:
        return {"status": 400, "error": {"code": exc.code, "message": exc.message}}
    except Exception as exc:
        return {"status": 500, "error": {"code": "internal_error", "message": str(exc)}}

@router.post("/coding-task/iteration-summary")
def coding_task_iteration_summary(req: CodingTaskContractReportRequest):
    start = time.time()
    eval_telemetry.log_event("action_called", endpoint="/agent/coding-task/iteration-summary", task_id=req.task_id)
    try:
        summary = task_ledger.iteration_summary(req.task_id)
        latency = round((time.time()-start)*1000,2)
        eval_telemetry.log_event("action_completed", endpoint="/agent/coding-task/iteration-summary", task_id=req.task_id, status=200, phase=summary.get("phase"), latency_ms=latency)
        return {"status": 200, "summary": summary, "latency_ms": latency, "timestamp": int(time.time()*1000)}
    except PolicyError as exc:
        return {"status": 400, "error": {"code": exc.code, "message": exc.message}}
    except Exception as exc:
        return {"status": 500, "error": {"code": "internal_error", "message": str(exc)}}

@router.post("/coding-task/contract-report")
def coding_task_contract_report(req: CodingTaskContractReportRequest):
    start = time.time()
    eval_telemetry.log_event("action_called", endpoint="/agent/coding-task/contract-report", task_id=req.task_id)
    try:
        contract = task_ledger.phase_contract(req.task_id)
        summary = task_ledger.iteration_summary(req.task_id)
        validation = task_ledger.validate_required_artifacts(req.task_id)
        latency = round((time.time()-start)*1000,2)
        eval_telemetry.log_event("action_completed", endpoint="/agent/coding-task/contract-report", task_id=req.task_id, status=200, phase=contract.get("phase"), contract_valid=validation.get("valid"), latency_ms=latency)
        return {"status": 200, "contract": contract, "summary": summary, "validation": validation, "latency_ms": latency, "timestamp": int(time.time()*1000)}
    except PolicyError as exc:
        return {"status": 400, "error": {"code": exc.code, "message": exc.message}}
    except Exception as exc:
        return {"status": 500, "error": {"code": "internal_error", "message": str(exc)}}


class CodingTaskSmokeTestRequest(BaseModel):
    repo_path: str
    task: str = "Smoke-test all uploadable Coding GPT core endpoints safely."
    safe_only: bool = True
    approval_policy: str = "safe_auto"
    max_iterations: int = 1


@router.post("/coding-task/smoke-test")
def coding_task_smoke_test(req: CodingTaskSmokeTestRequest):
    start = time.time()
    eval_telemetry.log_event("action_called", endpoint="/agent/coding-task/smoke-test", repo_path=req.repo_path, safe_only=req.safe_only)
    try:
        from routes import coding_dispatch
        checks = []

        def record(name: str, path: str, body: dict):
            ok = body.get("status") == 200 or isinstance(body.get("status"), str)
            checks.append({
                "name": name,
                "path": path,
                "ok": bool(ok),
                "status": body.get("status"),
                "error": body.get("error"),
            })
            return body

        init = coding_task(CodingTaskRequest(
            repo_path=req.repo_path,
            task=req.task,
            mode="plan_apply_verify",
            workspace_strategy="git_worktree",
            max_iterations=req.max_iterations,
            approval_policy=req.approval_policy,
            create_pr=False,
        ))
        record("01_agent_coding_task", "/agent/coding-task", init)
        task_id = init.get("task", {}).get("task_id") if isinstance(init, dict) else None
        workspace = init.get("workspace", {}).get("workspace_path") if isinstance(init, dict) else None
        if not task_id or not workspace:
            return {"status": 500, "error": {"code": "smoke_init_failed", "message": "Could not initialize task/workspace."}, "checks": checks}

        record("02_agent_next", "/agent/coding-task/next", coding_task_next(CodingTaskNextRequest(task_id=task_id)))
        record("03_agent_submit_artifact", "/agent/coding-task/submit", coding_task_submit(CodingTaskSubmitRequest(task_id=task_id, artifact_name="relevant_context", artifact={"smoke_test": True, "repo_path": req.repo_path})))
        record("04_agent_repair_plan", "/agent/coding-task/repair-plan", coding_task_repair_plan(CodingTaskRepairPlanRequest(task_id=task_id, max_files=5)))
        record("05_agent_iteration_summary", "/agent/coding-task/iteration-summary", coding_task_iteration_summary(CodingTaskContractReportRequest(task_id=task_id)))
        record("06_agent_contract_report", "/agent/coding-task/contract-report", coding_task_contract_report(CodingTaskContractReportRequest(task_id=task_id)))
        record("07_agent_finalize_no_commit", "/agent/coding-task/finalize", coding_task_finalize(CodingTaskFinalizeRequest(task_id=task_id, commit=False, create_pr=False, enforce_contract=False)))

        record("08_coding_universal_action", "/coding/action", coding_dispatch.coding_action(coding_dispatch.CodingActionRequest(category="diagnostics", action="triage", payload={"diagnostics": [{"tool": "pytest", "file": "tests/test_smoke.py", "message": "manual smoke diagnostic"}], "task": req.task})))
        record("09_coding_repo_action", "/coding/repo/action", coding_dispatch.repo_action(coding_dispatch.CategoryActionRequest(action="overview", payload={"repo_path": req.repo_path, "max_depth": 2})))
        record("10_coding_workspace_action", "/coding/workspace/action", coding_dispatch.workspace_action(coding_dispatch.CategoryActionRequest(action="status", payload={"workspace_path": workspace})))
        record("11_coding_patch_action", "/coding/patch/action", coding_dispatch.patch_action(coding_dispatch.CategoryActionRequest(action="history", payload={"workspace_path": workspace, "task_id": task_id})))
        record("12_coding_test_action", "/coding/test/action", coding_dispatch.test_action(coding_dispatch.CategoryActionRequest(action="discover", payload={"workspace_path": workspace})))
        record("13_coding_quality_action", "/coding/quality/action", coding_dispatch.quality_action(coding_dispatch.CategoryActionRequest(action="check", payload={"workspace_path": workspace, "timeout_seconds": 60})))
        record("14_coding_diagnostics_action", "/coding/diagnostics/action", coding_dispatch.diagnostics_action(coding_dispatch.CategoryActionRequest(action="parse", payload={"tool": "pytest", "stdout": "FAILED tests/test_x.py::test_x", "stderr": ""})))
        record("15_coding_policy_action", "/coding/policy/action", coding_dispatch.policy_action(coding_dispatch.CategoryActionRequest(action="check", payload={"path": "README.md", "repo_root": req.repo_path})))
        record("16_coding_tasks_action", "/coding/tasks/action", coding_dispatch.tasks_action(coding_dispatch.CategoryActionRequest(action="artifact_index", payload={"task_id": task_id})))
        record("17_coding_github_action", "/coding/github/action", coding_dispatch.github_action(coding_dispatch.CategoryActionRequest(action="checks_diagnose", payload={"checks": [{"name": "manual-smoke", "state": "success"}]})))
        record("18_coding_env_action", "/coding/env/action", coding_dispatch.env_action(coding_dispatch.CategoryActionRequest(action="discover", payload={"workspace_path": workspace})))

        passed = sum(1 for c in checks if c.get("ok"))
        report = {
            "repo_path": req.repo_path,
            "task_id": task_id,
            "workspace_path": workspace,
            "total": len(checks),
            "passed": passed,
            "failed": len(checks) - passed,
            "checks": checks,
            "notes": [
                "This safe smoke test uses an isolated worktree and does not commit, push, create PRs, install dependencies, or modify the primary checkout.",
                "Quality action success means the endpoint responded; the underlying repo quality command may still report passed=false if dependencies are missing.",
            ],
        }
        task_ledger.add_artifact(task_id, "smoke_test_report", report)
        latency = round((time.time() - start) * 1000, 2)
        eval_telemetry.log_event("action_completed", endpoint="/agent/coding-task/smoke-test", task_id=task_id, repo_path=req.repo_path, workspace_path=workspace, status=200, total=report.get("total"), passed=report.get("passed"), failed=report.get("failed"), latency_ms=latency)
        return {"status": 200, "smoke_test": report, "latency_ms": latency, "timestamp": int(time.time() * 1000)}
    except PolicyError as exc:
        return {"status": 400, "error": {"code": exc.code, "message": exc.message}}
    except Exception as exc:
        return {"status": 500, "error": {"code": "internal_error", "message": str(exc)}}
