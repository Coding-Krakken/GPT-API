from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from utils.auth import verify_key
from utils.policy import policy_result_for_path, evaluate_action, evaluate_action_deep

router = APIRouter(dependencies=[Depends(verify_key)])

class PolicyCheckRequest(BaseModel):
    path: str
    repo_root: str | None = None

class PolicyEvaluateActionRequest(BaseModel):
    action: str
    workspace_path: str | None = None
    changed_files: list[str] | None = None
    tests_passed: bool | None = None
    quality_passed: bool | None = None
    user_approved_network_write: bool = False

class PolicyEvaluateDeepRequest(PolicyEvaluateActionRequest):
    user_approved_sensitive: bool = False
    user_approved_large_diff: bool = False
    user_approved_deletions: bool = False
    diff_line_count: int = 0

@router.post("/check")
def policy_check(req: PolicyCheckRequest):
    result = policy_result_for_path(req.path, req.repo_root)
    result["status"] = 200 if result.get("allowed") else 400
    return result

@router.post("/evaluate-action")
def policy_evaluate_action(req: PolicyEvaluateActionRequest):
    result = evaluate_action(req.action, req.workspace_path, req.changed_files, req.tests_passed, req.quality_passed, req.user_approved_network_write)
    result["status"] = 200 if result.get("allowed") else 400
    return result

@router.post("/evaluate-action-deep")
def policy_evaluate_action_deep(req: PolicyEvaluateDeepRequest):
    result = evaluate_action_deep(
        req.action, req.workspace_path, req.changed_files, req.tests_passed, req.quality_passed,
        req.user_approved_network_write, req.user_approved_sensitive, req.user_approved_large_diff,
        req.user_approved_deletions, req.diff_line_count,
    )
    result["status"] = 200 if result.get("allowed") else 400
    return result
