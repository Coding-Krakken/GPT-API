from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import List, Dict, Any
from utils.auth import verify_key
import subprocess, os

router = APIRouter()



import traceback

class BatchRequest(BaseModel):
    operations: List[Dict[str, Any]]
    dry_run: bool = False

class Operation(BaseModel):
    action: str
    args: Dict[str, Any]

@router.post("/batch")
async def batch_ops(request: Request):
    try:
        body = await request.json()
        operations = body.get("operations")
        if not isinstance(operations, list):
            raise HTTPException(status_code=400, detail="'operations' must be a list of operation objects.")
        results = []
        for idx, op in enumerate(operations):
            if not isinstance(op, dict):
                results.append({"error": f"Operation at index {idx} is not a valid object."})
                continue
            action = op.get("action")
            args = op.get("args", {})
            if not action or not isinstance(action, str):
                results.append({"error": f"Missing or invalid 'action' in operation at index {idx}."})
                continue
            # Here you would dispatch to the correct handler based on action
            # For now, just echo the operation
            results.append({"action": action, "args": args})
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid batch request: {e}")



# Accept both /batch and /batch/ and both Pydantic and raw JSON for maximum compatibility
@router.post("/", dependencies=[Depends(verify_key)])
@router.post("", dependencies=[Depends(verify_key)])
async def run_batch(req: BatchRequest = None, request: Request = None):
    # Try to parse as Pydantic first, fallback to raw JSON
    if req is None:
        try:
            data = await request.json()
            operations = data.get("operations")
            dry_run = data.get("dry_run", False)
            if not isinstance(operations, list):
                return {"error": "Request body must include 'operations' as a list of operation objects."}
            req = BatchRequest(operations=operations, dry_run=dry_run)
        except Exception as e:
            return {"error": f"Invalid JSON or missing fields: {str(e)}"}
    if not hasattr(req, 'operations') or not isinstance(req.operations, list):
        return {"error": "Request body must include 'operations' as a list of operation objects."}
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
