from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import List, Dict, Any
from utils.auth import verify_key
import subprocess, os
from routes.files import handle_file_operation, FileRequest
from routes.code import handle_code_action  # Assuming similar pattern

router = APIRouter()



import traceback

class BatchRequest(BaseModel):
    operations: List[Dict[str, Any]]
    dry_run: bool = False

class Operation(BaseModel):
    action: str
    args: Dict[str, Any]





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
                return {"error": {"code": "invalid_batch", "message": "Request body must include 'operations' as a list of operation objects."}, "status": 400}
            req = BatchRequest(operations=operations, dry_run=dry_run)
        except Exception as e:
            return {"error": {"code": "invalid_json", "message": f"Invalid JSON or missing fields: {str(e)}"}, "status": 400}
    if not hasattr(req, 'operations') or not isinstance(req.operations, list):
        return {"error": {"code": "invalid_batch", "message": "Request body must include 'operations' as a list of operation objects."}, "status": 400}
    results = []
    for idx, op in enumerate(req.operations):
        try:
            if not isinstance(op, dict):
                results.append({"error": {"code": "invalid_operation", "message": f"Operation at index {idx} is not a valid object."}, "status": 400})
                continue
            action = op.get("action")
            if not action or not isinstance(action, str):
                results.append({"error": {"code": "missing_action", "message": f"Missing or invalid 'action' in operation at index {idx}."}, "status": 400})
                continue
            if req.dry_run:
                results.append({"action": action, "dry_run": True, "args": op})
                continue
            if action == "shell":
                cmd = op.get("command") or op.get("args", {}).get("command")
                if not cmd:
                    results.append({"action": action, "error": {"code": "missing_command", "message": "Missing 'command' for shell action"}, "status": 400})
                    continue
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                results.append({
                    "action": action,
                    "stdout": result.stdout.strip(),
                    "stderr": result.stderr.strip(),
                    "exit_code": result.returncode,
                    "status": 200 if result.returncode == 0 else 400
                })
            elif action == "files":
                file_args = op.get("args", op)
                try:
                    resp = handle_file_operation(FileRequest(**file_args))
                    results.append({"action": action, "result": resp})
                except Exception as e:
                    results.append({"action": action, "error": {"code": "files_error", "message": str(e)}, "status": 500})
            elif action == "code":
                code_args = op.get("args", op)
                try:
                    resp = handle_code_action(code_args)
                    results.append({"action": action, "result": resp})
                except Exception as e:
                    results.append({"action": action, "error": {"code": "code_error", "message": str(e)}, "status": 500})
            else:
                results.append({"action": action, "error": {"code": "unsupported_action", "message": "Unsupported action in batch"}, "status": 400})
        except Exception as e:
            results.append({"action": op.get("action"), "error": {"code": "internal_error", "message": str(e)}, "trace": traceback.format_exc(), "status": 500})
    return {"results": results}
