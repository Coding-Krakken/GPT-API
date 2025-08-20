from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any
from utils.auth import verify_key
import subprocess, os

router = APIRouter()

class Operation(BaseModel):
    action: str
    args: Dict[str, Any]

class BatchRequest(BaseModel):
    operations: List[Operation]

@router.post("/", dependencies=[Depends(verify_key)])
def run_batch(req: BatchRequest):
    results = []
    for op in req.operations:
        try:
            if op.action == "shell":
                cmd = op.args.get("command", "")
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                results.append({
                    "action": op.action,
                    "stdout": result.stdout.strip(),
                    "stderr": result.stderr.strip(),
                    "exit_code": result.returncode
                })
            else:
                results.append({"action": op.action, "error": "Unsupported action in batch"})
        except Exception as e:
            results.append({"action": op.action, "error": str(e)})

    return {"results": results}
