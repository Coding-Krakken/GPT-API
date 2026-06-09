from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from utils.auth import verify_key
from utils.policy import PolicyError
from utils import github_safe, task_ledger

router = APIRouter(dependencies=[Depends(verify_key)])

class GithubIssueReadRequest(BaseModel): workspace_path: str; issue: str
class GithubPrReadRequest(BaseModel): workspace_path: str; pr: str
class GithubChecksReadRequest(BaseModel): workspace_path: str; ref: str | None = None
class GithubPrCommentRequest(BaseModel): workspace_path: str; pr: str; body: str; dry_run: bool = True
class GithubPrCreateFromTaskRequest(BaseModel): workspace_path: str; task_id: str; title: str | None = None; dry_run: bool = True
class GithubChecksDiagnoseRequest(BaseModel): checks: list[dict[str, Any]]
class GithubApplyFeedbackPlanRequest(BaseModel): workspace_path: str; comments: list[dict[str, Any]]

def _wrap(fn, *args):
    start = time.time()
    try:
        out = fn(*args)
        out.update({"status": 200, "latency_ms": round((time.time() - start) * 1000, 2), "timestamp": int(time.time() * 1000)})
        return out
    except PolicyError as exc:
        return {"status": 400, "error": {"code": exc.code, "message": exc.message}}
    except Exception as exc:
        return {"status": 500, "error": {"code": "internal_error", "message": str(exc)}}

@router.post("/issue/read")
def issue_read(req: GithubIssueReadRequest): return _wrap(github_safe.issue_read, req.workspace_path, req.issue)

@router.post("/pr/read")
def pr_read(req: GithubPrReadRequest): return _wrap(github_safe.pr_read, req.workspace_path, req.pr)

@router.post("/checks/read")
def checks_read(req: GithubChecksReadRequest): return _wrap(github_safe.checks_read, req.workspace_path, req.ref)

@router.post("/pr/comment")
def pr_comment(req: GithubPrCommentRequest): return _wrap(github_safe.pr_comment, req.workspace_path, req.pr, req.body, req.dry_run)

@router.post("/pr/create-from-task")
def pr_create_from_task(req: GithubPrCreateFromTaskRequest):
    task = task_ledger.read(req.task_id)
    return _wrap(github_safe.pr_create_from_task, req.workspace_path, task, req.title, req.dry_run)

@router.post("/checks/diagnose")
def checks_diagnose(req: GithubChecksDiagnoseRequest): return _wrap(github_safe.checks_diagnose, req.checks)

@router.post("/pr/apply-feedback-plan")
def apply_feedback_plan(req: GithubApplyFeedbackPlanRequest): return _wrap(github_safe.apply_feedback_plan, req.workspace_path, req.comments)


class GithubPrUpdateBodyRequest(BaseModel):
    workspace_path: str
    pr: str
    body: str
    dry_run: bool = True

class GithubReviewCommentsRequest(BaseModel):
    workspace_path: str
    pr: str

class GithubChecksLogsRequest(BaseModel):
    workspace_path: str
    ref: str | None = None
    dry_run: bool = True

class GithubBranchPushRequest(BaseModel):
    workspace_path: str
    remote: str = "origin"
    branch: str | None = None
    dry_run: bool = True

@router.post("/pr/update-body")
def pr_update_body(req: GithubPrUpdateBodyRequest): return _wrap(github_safe.pr_update_body, req.workspace_path, req.pr, req.body, req.dry_run)

@router.post("/pr/review-comments")
def pr_review_comments(req: GithubReviewCommentsRequest): return _wrap(github_safe.review_comments, req.workspace_path, req.pr)

@router.post("/checks/logs")
def checks_logs(req: GithubChecksLogsRequest): return _wrap(github_safe.checks_logs, req.workspace_path, req.ref, req.dry_run)

@router.post("/branch/push")
def branch_push(req: GithubBranchPushRequest): return _wrap(github_safe.branch_push, req.workspace_path, req.remote, req.branch, req.dry_run)


class GithubCiRepairPlanRequest(BaseModel):
    workspace_path: str
    checks: list[dict[str, Any]] | None = None
    logs: str | None = None

class GithubFeedbackContractRequest(BaseModel):
    workspace_path: str
    comments: list[dict[str, Any]]

@router.post("/checks/repair-plan")
def checks_repair_plan(req: GithubCiRepairPlanRequest): return _wrap(github_safe.ci_repair_plan, req.workspace_path, req.checks, req.logs)

@router.post("/pr/feedback-to-patch-contract")
def feedback_to_patch_contract(req: GithubFeedbackContractRequest): return _wrap(github_safe.feedback_to_patch_contract, req.workspace_path, req.comments)
