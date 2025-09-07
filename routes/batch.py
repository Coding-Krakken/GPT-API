from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any
from utils.auth import verify_key
import subprocess, os

router = APIRouter()



import traceback

class BatchRequest(BaseModel):
    operations: List[Dict[str, Any]]
    dry_run: bool = False


@router.post("/", dependencies=[Depends(verify_key)])
def run_batch(req: BatchRequest):
    results = []
    for op in req.operations:
        try:
            action = op.get("action")
            if req.dry_run:
                results.append({"action": action, "dry_run": True, "args": op})
                continue
            if action == "shell":
                cmd = op.get("command") or op.get("args", {}).get("command")
                if not cmd:
                    raise ValueError("Missing 'command' for shell action")
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                results.append({
                    "action": action,
                    "stdout": result.stdout.strip(),
                    "stderr": result.stderr.strip(),
                    "exit_code": result.returncode
                })
            elif action == "files":
                # You can implement or import file handling logic here
                results.append({"action": action, "error": "File batch ops not implemented"})
            elif action == "code":
                # You can implement or import code handling logic here
                results.append({"action": action, "error": "Code batch ops not implemented"})
            else:
                results.append({"action": action, "error": "Unsupported action in batch"})
        except Exception as e:
            results.append({"action": op.get("action"), "error": str(e), "trace": traceback.format_exc()})
    return {"results": results}
