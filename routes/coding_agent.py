from __future__ import annotations

import re
import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from utils.auth import verify_key
from utils.policy import PolicyError
from utils import repo_intel, worktrees, test_discovery

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


def _slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", text.lower()).strip("-")[:60] or "coding-task"


@router.post("/coding-task")
def coding_task(req: CodingTaskRequest):
    start = time.time()
    try:
        if req.mode != "plan_apply_verify":
            return {"error": {"code": "unsupported_mode", "message": "Only plan_apply_verify is supported."}, "status": 400}
        if req.workspace_strategy != "git_worktree":
            return {"error": {"code": "unsupported_workspace_strategy", "message": "Only git_worktree is supported."}, "status": 400}
        overview = repo_intel.overview(req.repo_path, 4)
        workspace = worktrees.create_worktree(req.repo_path, _slug(req.task), req.base_branch)
        tests = test_discovery.discover(workspace["workspace_path"])
        plan = [
            "Inspect repository overview and current git state.",
            "Use the isolated worktree for all changes.",
            "Search and read focused context relevant to the task.",
            "Apply only policy-checked patches via /patch/preview and /patch/apply.",
            "Run discovered focused tests, then broader quality checks when available.",
            "Return final diff, tests run, risks, and next steps.",
        ]
        return {
            "status": "workspace_ready",
            "message": "Coding task initialized safely. Continue with /repo/search, /repo/read-context, /patch/preview, /patch/apply, /test/run, /quality/check, and /workspace/diff.",
            "workspace": workspace,
            "overview": overview,
            "test_discovery": tests,
            "plan": plan,
            "max_iterations": min(max(req.max_iterations, 1), 10),
            "create_pr": req.create_pr,
            "latency_ms": round((time.time() - start) * 1000, 2),
            "timestamp": int(time.time() * 1000),
        }
    except PolicyError as exc:
        return {"error": {"code": exc.code, "message": exc.message}, "status": 400}
    except Exception as exc:
        return {"error": {"code": "internal_error", "message": str(exc)}, "status": 500}
