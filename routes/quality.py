from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from utils.auth import verify_key
from utils.policy import PolicyError
from utils.safe_subprocess import run_checked
from utils.test_discovery import quality_commands

router = APIRouter(dependencies=[Depends(verify_key)])


class QualityCheckRequest(BaseModel):
    workspace_path: str
    timeout_seconds: int = 120


@router.post("/check")
@router.post("/run")
def quality_check(req: QualityCheckRequest):
    start = time.time()
    try:
        results = []
        for cmd in quality_commands(req.workspace_path):
            result = run_checked(cmd["argv"], req.workspace_path, timeout=req.timeout_seconds)
            results.append({"name": cmd["name"], "argv": cmd["argv"], "passed": result["passed"], "exit_code": result["exit_code"], "stdout_tail": result["stdout"][-4000:], "stderr_tail": result["stderr"][-4000:]})
        return {"passed": all(r["passed"] for r in results), "results": results, "status": 200, "latency_ms": round((time.time() - start) * 1000, 2), "timestamp": int(time.time() * 1000)}
    except PolicyError as exc:
        return {"error": {"code": exc.code, "message": exc.message}, "status": 400}
    except Exception as exc:
        return {"error": {"code": "internal_error", "message": str(exc)}, "status": 500}
