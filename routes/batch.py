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
async def run_batch(request: Request):
    # Always parse as raw JSON to avoid Pydantic validation issues
    try:
        data = await request.json()
        operations = data.get("operations")
        dry_run = data.get("dry_run", False)
        if not isinstance(operations, list):
            return {"error": {"code": "invalid_batch", "message": "Request body must include 'operations' as a list of operation objects."}, "status": 400}
        req = type('BatchRequest', (), {'operations': operations, 'dry_run': dry_run})()
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
                cmd = op.get("command") or (op.get("args") or {}).get("command")
                if not cmd:
                    results.append({"action": action, "error": {"code": "missing_command", "message": "Missing 'command' for shell action"}, "status": 400})
                    continue
                try:
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    results.append({
                        "action": action,
                        "stdout": result.stdout.strip(),
                        "stderr": result.stderr.strip(),
                        "exit_code": result.returncode,
                        "status": 200 if result.returncode == 0 else 400
                    })
                except Exception as e:
                    results.append({"action": action, "error": {"code": "subprocess_error", "message": str(e)}, "status": 500})
            elif action == "files":
                file_args = op.get("args", op)
                try:
                    resp = handle_file_operation(FileRequest(**file_args))
                    # For files, merge the result structure to avoid double nesting
                    if "result" in resp and isinstance(resp["result"], dict):
                        file_result = resp["result"]
                        file_result.update({"latency_ms": resp.get("latency_ms"), "payload_size": resp.get("payload_size")})
                        results.append({"action": action, "result": file_result})
                    else:
                        results.append({"action": action, "result": resp})
                except Exception as e:
                    results.append({"action": action, "error": {"code": "files_error", "message": str(e)}, "status": 500})
            elif action == "code":
                from routes.code import CodeAction
                code_args = op.get("args", op)
                try:
                    if not isinstance(code_args, CodeAction):
                        code_args = CodeAction(**code_args)
                    resp = handle_code_action(code_args)
                    if isinstance(resp, dict) and 'result' in resp and 'error' in resp['result']:
                        # Handle new code endpoint error structure
                        results.append({"action": action, "result": resp['result']})
                    elif isinstance(resp, dict) and 'error' in resp:
                        # Handle old error structure for backward compatibility
                        results.append({"action": action, "error": resp['error'], "status": resp.get('status', 400)})
                    else:
                        # For code actions, flatten the nested result structure
                        if isinstance(resp, dict) and "result" in resp:
                            code_result = resp["result"]
                            results.append({"action": action, "result": code_result})
                        else:
                            results.append({"action": action, "result": resp})
                except HTTPException as e:
                    detail = getattr(e, 'detail', None)
                    if isinstance(detail, dict) and 'error' in detail:
                        results.append({"action": action, "error": detail['error'], "status": getattr(e, 'status_code', 500)})
                    else:
                        results.append({"action": action, "error": {"code": "code_error", "message": str(e)}, "status": getattr(e, 'status_code', 500)})
                except Exception as e:
                    results.append({"action": action, "error": {"code": "code_error", "message": str(e)}, "status": 500})
            else:
                results.append({"action": action, "error": {"code": "unsupported_action", "message": "Unsupported action in batch"}, "status": 400})
        except Exception as e:
            results.append({"action": op.get("action"), "error": {"code": "internal_error", "message": str(e)}, "status": 500})
    return {"results": results}
