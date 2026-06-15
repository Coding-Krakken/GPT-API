from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from utils.auth import verify_key
from utils.policy import PolicyError
from utils.test_discovery import quality_commands
from utils.validation_workflow import git_preflight, run_validation_command

router = APIRouter(dependencies=[Depends(verify_key)])


class QualityCheckRequest(BaseModel):
    workspace_path: str
    timeout_seconds: int = 120
    validationMode: str | None = None
    target_ref: str | None = None


@router.post("/check")
@router.post("/run")
def quality_check(req: QualityCheckRequest):
    start = time.time()
    try:
        results = []
        preflight = git_preflight(req.workspace_path)
        commands = quality_commands(req.workspace_path)
        if not commands:
            not_run = {
                "name": "quality",
                "command": "",
                "status": "not_run",
                "exitCode": None,
                "durationMs": 0,
                "scope": "dirty-worktree" if preflight.get("isDirty") else "clean-head",
                "summary": "No quality commands were discovered.",
                "confidenceImpact": "High",
                "preflight": preflight,
            }
            return {"passed": False, "results": [], "notRun": [not_run], "repoPreflight": preflight, "status": 200, "latency_ms": round((time.time() - start) * 1000, 2), "timestamp": int(time.time() * 1000)}
        for cmd in commands:
            result = run_validation_command(name=cmd["name"], argv=cmd["argv"], cwd=req.workspace_path, timeout_seconds=req.timeout_seconds, validation_mode=req.validationMode, target_ref=req.target_ref)
            results.append({"name": cmd["name"], "argv": cmd["argv"], "passed": result["status"] == "passed", "exit_code": result["exitCode"], "stdout_tail": result.get("stdout_tail", ""), "stderr_tail": result.get("stderr_tail", ""), "validationResult": result})
        return {"passed": all(r["passed"] for r in results), "results": results, "repoPreflight": preflight, "status": 200, "latency_ms": round((time.time() - start) * 1000, 2), "timestamp": int(time.time() * 1000)}
    except PolicyError as exc:
        return {"error": {"code": exc.code, "message": exc.message}, "status": 400}
    except Exception as exc:
        return {"error": {"code": "internal_error", "message": str(exc)}, "status": 500}
