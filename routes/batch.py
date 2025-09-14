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
    errors = []
    
    for idx, op in enumerate(req.operations):
        try:
            if not isinstance(op, dict):
                error_result = {"error": {"code": "invalid_operation", "message": f"Operation at index {idx} is not a valid object."}, "status": 400, "operation_index": idx}
                results.append(error_result)
                errors.append(error_result)
                continue
            action = op.get("action")
            if not action or not isinstance(action, str):
                error_result = {"error": {"code": "missing_action", "message": f"Missing or invalid 'action' in operation at index {idx}."}, "status": 400, "operation_index": idx}
                results.append(error_result)
                errors.append(error_result)
                continue
            if req.dry_run:
                results.append({"action": action, "dry_run": True, "args": op, "operation_index": idx})
                continue
            if action == "shell":
                cmd = op.get("command") or (op.get("args") or {}).get("command")
                if not cmd:
                    error_result = {"action": action, "error": {"code": "missing_command", "message": "Missing 'command' for shell action"}, "status": 400, "operation_index": idx}
                    results.append(error_result)
                    errors.append(error_result)
                    continue
                try:
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    shell_result = {
                        "action": action,
                        "stdout": result.stdout.strip(),
                        "stderr": result.stderr.strip(),
                        "exit_code": result.returncode,
                        "status": 200 if result.returncode == 0 else 400,
                        "operation_index": idx
                    }
                    results.append(shell_result)
                    # Add shell command failures to errors array
                    if result.returncode != 0:
                        error_result = {
                            "action": action,
                            "error": {
                                "code": "shell_execution_failed",
                                "message": f"Command failed with exit code {result.returncode}",
                                "command": cmd,
                                "stderr": result.stderr.strip()
                            },
                            "status": 400,
                            "operation_index": idx
                        }
                        errors.append(error_result)
                except Exception as e:
                    error_result = {"action": action, "error": {"code": "subprocess_error", "message": str(e)}, "status": 500, "operation_index": idx}
                    results.append(error_result)
                    errors.append(error_result)
            elif action == "files":
                file_args = op.get("args", op)
                try:
                    resp = handle_file_operation(FileRequest(**file_args))
                    # For files, merge the result structure to avoid double nesting
                    if "result" in resp and isinstance(resp["result"], dict):
                        file_result = resp["result"]
                        file_result.update({"latency_ms": resp.get("latency_ms"), "payload_size": resp.get("payload_size"), "operation_index": idx})
                        result_obj = {"action": action, "result": file_result}
                        results.append(result_obj)
                        # Check if file operation had errors
                        if "error" in file_result:
                            errors.append({"action": action, "error": file_result["error"], "status": resp.get("status", 500), "operation_index": idx})
                    else:
                        result_obj = {"action": action, "result": resp, "operation_index": idx}
                        results.append(result_obj)
                        if isinstance(resp, dict) and "error" in resp:
                            errors.append({"action": action, "error": resp["error"], "status": resp.get("status", 500), "operation_index": idx})
                except Exception as e:
                    error_result = {"action": action, "error": {"code": "files_error", "message": str(e)}, "status": 500, "operation_index": idx}
                    results.append(error_result)
                    errors.append(error_result)
            elif action == "code":
                from routes.code import CodeAction
                code_args = op.get("args", op)
                try:
                    if not isinstance(code_args, CodeAction):
                        code_args = CodeAction(**code_args)
                    resp = handle_code_action(code_args)
                    if isinstance(resp, dict) and 'result' in resp and 'error' in resp['result']:
                        # Handle new code endpoint error structure
                        result_obj = {"action": action, "result": resp['result'], "operation_index": idx}
                        results.append(result_obj)
                        errors.append({"action": action, "error": resp['result']['error'], "status": resp['result'].get('status', 400), "operation_index": idx})
                    elif isinstance(resp, dict) and 'error' in resp:
                        # Handle old error structure for backward compatibility
                        error_result = {"action": action, "error": resp['error'], "status": resp.get('status', 400), "operation_index": idx}
                        results.append(error_result)
                        errors.append(error_result)
                    else:
                        # For code actions, flatten the nested result structure
                        if isinstance(resp, dict) and "result" in resp:
                            code_result = resp["result"]
                            code_result["operation_index"] = idx
                            result_obj = {"action": action, "result": code_result}
                            results.append(result_obj)
                            # Check if code result has errors
                            if "error" in code_result:
                                errors.append({"action": action, "error": code_result["error"], "status": code_result.get("status", 400), "operation_index": idx})
                        else:
                            results.append({"action": action, "result": resp, "operation_index": idx})
                except HTTPException as e:
                    detail = getattr(e, 'detail', None)
                    if isinstance(detail, dict) and 'error' in detail:
                        error_result = {"action": action, "error": detail['error'], "status": getattr(e, 'status_code', 500), "operation_index": idx}
                        results.append(error_result)
                        errors.append(error_result)
                    else:
                        error_result = {"action": action, "error": {"code": "code_error", "message": str(e)}, "status": getattr(e, 'status_code', 500), "operation_index": idx}
                        results.append(error_result)
                        errors.append(error_result)
                except Exception as e:
                    error_result = {"action": action, "error": {"code": "code_error", "message": str(e)}, "status": 500, "operation_index": idx}
                    results.append(error_result)
                    errors.append(error_result)
            else:
                error_result = {"action": action, "error": {"code": "unsupported_action", "message": "Unsupported action in batch"}, "status": 400, "operation_index": idx}
                results.append(error_result)
                errors.append(error_result)
        except Exception as e:
            error_result = {"action": op.get("action"), "error": {"code": "internal_error", "message": str(e)}, "status": 500, "operation_index": idx}
            results.append(error_result)
            errors.append(error_result)
    
    # Return results with comprehensive error reporting
    return {
        "results": results,
        "errors": errors,
        "summary": {
            "total_operations": len(req.operations),
            "successful_operations": len(results) - len(errors),
            "failed_operations": len(errors),
            "dry_run": req.dry_run
        }
    }
