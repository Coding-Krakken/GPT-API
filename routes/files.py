from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import os, shutil
import time
from utils.auth import verify_key

router = APIRouter()


# Support both single and batch file operations
from typing import List, Optional, Union

class FileOp(BaseModel):
    action: str
    path: str
    target_path: Optional[str] = None
    content: Optional[str] = None
    fault: Optional[str] = None
    recursive: bool = False

class FileRequest(BaseModel):
    action: Optional[str] = None
    path: Optional[str] = None
    target_path: Optional[str] = None
    content: Optional[str] = None
    fault: Optional[str] = None
    recursive: bool = False
    operations: Optional[List[FileOp]] = None


def _do_file_op(op: FileOp):
    # Validate required fields
    if not op.action or not op.path:
        return {"error": {"code": "missing_field", "message": "Missing required field: 'action' or 'path'"}, "status": 400}
    path = os.path.abspath(os.path.expanduser(op.path))
    target = os.path.abspath(os.path.expanduser(op.target_path)) if op.target_path else None
    try:
        if op.fault == 'permission':
            return {"error": {"code": "permission_denied", "message": "Permission denied"}, "status": 403}
        if op.fault == 'io':
            return {"error": {"code": "io_error", "message": "I/O error occurred"}, "status": 500}
        if op.action == "read":
            if not os.path.exists(path):
                return {"error": {"code": "not_found", "message": f"File '{path}' does not exist."}, "status": 404}
            with open(path, "r", encoding="utf-8") as f:
                return {"content": f.read(), "status": 200}
        elif op.action == "write":
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(op.content or "")
            return {"status": 200, "message": f"Wrote to {path}"}
        elif op.action == "delete":
            if not os.path.exists(path):
                return {"error": {"code": "not_found", "message": f"File or directory '{path}' does not exist."}, "status": 404}
            if os.path.isdir(path) and op.recursive:
                shutil.rmtree(path)
            else:
                os.remove(path)
            return {"status": 200, "message": f"Deleted {path}"}
        elif op.action == "copy":
            if not os.path.exists(path):
                return {"error": {"code": "not_found", "message": f"Source '{path}' does not exist."}, "status": 404}
            if not target:
                return {"error": {"code": "missing_target", "message": "Target path required for copy."}, "status": 400}
            if os.path.isdir(path):
                shutil.copytree(path, target)
            else:
                shutil.copy2(path, target)
            return {"status": 200, "message": f"Copied {path} to {target}"}
        elif op.action == "move":
            if not os.path.exists(path):
                return {"error": {"code": "not_found", "message": f"Source '{path}' does not exist."}, "status": 404}
            if not target:
                return {"error": {"code": "missing_target", "message": "Target path required for move."}, "status": 400}
            shutil.move(path, target)
            return {"status": 200, "message": f"Moved {path} to {target}"}
        elif op.action == "stat":
            if not os.path.exists(path):
                return {"error": {"code": "not_found", "message": f"File or directory '{path}' does not exist."}, "status": 404}
            stats = os.stat(path)
            return {"size": stats.st_size, "mtime": stats.st_mtime, "ctime": stats.st_ctime, "status": 200}
        elif op.action == "exists":
            return {"exists": os.path.exists(path), "status": 200}
        elif op.action == "list":
            if not os.path.isdir(path):
                return {"error": {"code": "not_a_directory", "message": "Path is not a directory."}, "status": 400}
            return {"items": os.listdir(path), "status": 200}
        else:
            return {"error": {"code": "unsupported_action", "message": f"Unsupported action: {op.action}"}, "status": 400}
    except Exception as e:
        return {"error": {"code": "internal_error", "message": str(e)}, "status": 500}

@router.post("/", dependencies=[Depends(verify_key)])
def handle_file_operation(req: FileRequest):
    start = time.time()
    payload_size = None
    try:
        # Support batch (operations) or single
        if req.operations:
            if not isinstance(req.operations, list) or len(req.operations) == 0:
                return {"error": {"code": "invalid_batch", "message": "'operations' must be a non-empty list of file operations."}, "status": 400}
            from fastapi.encoders import jsonable_encoder
            results = []
            for op in req.operations:
                # Ensure op is a FileOp instance or dict
                if isinstance(op, dict):
                    op_obj = FileOp(**op)
                else:
                    op_obj = op
                results.append(_do_file_op(op_obj))
            latency = round((time.time() - start) * 1000, 2)
            payload_size = len(str(req.model_dump()))
            return jsonable_encoder({"results": results, "latency_ms": latency, "payload_size": payload_size, "timestamp": int(time.time() * 1000)})
        # Single op
        if not req.action or not req.path:
            return {"error": {"code": "missing_field", "message": "Missing required field: 'action' or 'path'"}, "status": 400}
        op = FileOp(
            action=req.action,
            path=req.path,
            target_path=req.target_path,
            content=req.content,
            fault=req.fault,
            recursive=req.recursive
        )
        result = _do_file_op(op)
        latency = round((time.time() - start) * 1000, 2)
        payload_size = len(str(req.model_dump()))
        return {"result": result, "latency_ms": latency, "payload_size": payload_size, "timestamp": int(time.time() * 1000)}
    except Exception as e:
        return {"error": {"code": "internal_error", "message": str(e)}, "status": 500}
