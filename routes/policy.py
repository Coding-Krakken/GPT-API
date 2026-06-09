from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from utils.auth import verify_key
from utils.policy import policy_result_for_path

router = APIRouter(dependencies=[Depends(verify_key)])


class PolicyCheckRequest(BaseModel):
    path: str
    repo_root: str | None = None


@router.post("/check")
def policy_check(req: PolicyCheckRequest):
    result = policy_result_for_path(req.path, req.repo_root)
    result["status"] = 200 if result.get("allowed") else 400
    return result
