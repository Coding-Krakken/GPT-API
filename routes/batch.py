from fastapi import APIRouter, Depends, Request
from typing import Dict, Any, List
from utils.auth import verify_key
import time
import asyncio
import subprocess
import os

router = APIRouter()


def _status(result):
    if isinstance(result, dict):
        if result.get("status"):
            return int(result.get("status"))
        inner = result.get("result")
        if isinstance(inner, dict) and inner.get("status"):
            return int(inner.get("status"))
        if result.get("exit_code") not in [None, 0]:
            return 400
    return 200


def _payload(op):
    return op.get("payload") or op.get("args") or {k: v for k, v in op.items() if k not in ["id", "endpoint", "depends_on", "rollback"]}


def _endpoint(op):
    return op.get("endpoint") or op.get("action")


def _run_shell_payload(payload):
    cmd = payload.get("command")
    if not cmd:
        return {"error": {"code": "missing_command", "message": "Missing command"}, "status": 400}
    if payload.get("dry_run"):
        return {"stdout": cmd, "stderr": "", "exit_code": 0, "dry_run": True, "status": 200}
    r = subprocess.run(cmd, shell=True, cwd=payload.get("working_dir"), input=payload.get("stdin"), capture_output=True, text=True, timeout=min(int(payload.get("timeout_seconds") or 300), 3600))
    return {"stdout": r.stdout, "stderr": r.stderr, "exit_code": r.returncode, "status": 200 if r.returncode == 0 else 400}


def _execute_sync(endpoint: str, payload: Dict[str, Any]):
    if endpoint == "shell":
        return _run_shell_payload(payload)
    if endpoint == "files":
        from routes.files import handle_file_operation, FileRequest
        resp = handle_file_operation(FileRequest(**payload))
        return resp.get("result", resp) if isinstance(resp, dict) else resp
    if endpoint == "code":
        from routes.code import handle_code_action, CodeAction
        resp = handle_code_action(CodeAction(**payload))
        return resp.get("result", resp) if isinstance(resp, dict) else resp
    if endpoint == "git":
        from routes.git import handle_git_command, GitRequest
        return handle_git_command(GitRequest(**payload))
    if endpoint == "package":
        # Use dry-run-style direct process semantics for sync batch compatibility.
        from routes.package import PackageRequest, _cmd
        req = PackageRequest(**payload)
        argv = _cmd(req)
        if req.dry_run:
            import shlex
            return {"stdout": shlex.join(argv), "stderr": "", "exit_code": 0, "dry_run": True, "status": 200}
        r = subprocess.run(argv, cwd=req.working_dir, capture_output=True, text=True, timeout=req.timeout_seconds)
        return {"stdout": r.stdout, "stderr": r.stderr, "exit_code": r.returncode, "status": 200 if r.returncode == 0 else 400}
    if endpoint == "refactor":
        # Refactor route is async Request-based; provide literal batch implementation for common mode.
        import re, difflib
        files = payload.get("files") or []
        search = payload.get("search", "")
        replace = payload.get("replace", "")
        mode = payload.get("mode", "literal")
        dry = payload.get("dry_run", False) or payload.get("preview", False) or not payload.get("apply", False)
        results, diffs = [], []
        for f in files:
            p = os.path.abspath(os.path.expanduser(f))
            if not os.path.isfile(p):
                continue
            old = open(p, encoding="utf-8", errors="replace").read()
            new = re.sub(search, replace, old) if mode == "regex" else old.replace(search, replace)
            if old != new:
                diffs.append("\n".join(difflib.unified_diff(old.splitlines(), new.splitlines(), fromfile=p, tofile=p, lineterm="")))
                if not dry:
                    open(p, "w", encoding="utf-8").write(new)
            results.append({"file": p, "changed": old != new})
        return {"results": results, "diff": "\n".join(diffs), "status": 200}
    if endpoint == "system":
        from routes.system import get_system_info
        return get_system_info()
    if endpoint == "monitor":
        from routes.monitor import monitor_system, MonitorRequest
        return monitor_system(MonitorRequest(**payload))
    if endpoint == "batch":
        return {"error": {"code": "recursive_batch_blocked", "message": "Nested batch execution is not supported in-process."}, "status": 400}
    return {"error": {"code": "unsupported_action", "message": f"Unsupported action in batch: {endpoint}"}, "status": 400}


async def _run_one(op):
    endpoint = _endpoint(op)
    if not endpoint:
        return {"action": None, "error": {"code": "missing_action", "message": "Missing action or endpoint"}, "status": 400}
    payload = _payload(op)
    
    result = await asyncio.to_thread(_execute_sync, endpoint, payload)
    item = {"id": op.get("id"), "action": endpoint, "endpoint": endpoint, "result": result}
    if isinstance(result, dict):
        item.update({k: v for k, v in result.items() if k not in item})
    return item


@router.post("/", dependencies=[Depends(verify_key)])
@router.post("", dependencies=[Depends(verify_key)])
async def run_batch(request: Request):
    start = time.time()
    try:
        data = await request.json()
        operations = data.get("operations")
        if not isinstance(operations, list):
            return {"error": {"code": "invalid_batch", "message": "operations must be a list"}, "status": 400}
        if not operations:
            return {"ok": True, "results": [], "latency_ms": round((time.time()-start)*1000,2), "timestamp": int(time.time()*1000)}
        mode = data.get("mode") or ("dry_run" if data.get("dry_run") else "sequential")
        stop_on_error = data.get("stop_on_error", False)
        rollback_on_error = data.get("rollback_on_error", False)
        if mode == "dry_run":
            return {"ok": True, "results": [{"id": op.get("id"), "action": _endpoint(op), "endpoint": _endpoint(op), "dry_run": True, "payload": _payload(op)} for op in operations], "latency_ms": round((time.time()-start)*1000,2), "timestamp": int(time.time()*1000)}
        results: List[dict] = []
        completed = set()
        failed_id = None
        if mode == "parallel":
            results = await asyncio.gather(*[_run_one(op) for op in operations if isinstance(op, dict)])
            for i, op in enumerate(operations):
                if not isinstance(op, dict):
                    results.insert(i, {"action": None, "error": {"code": "invalid_operation", "message": "Operation must be an object"}, "status": 400})
            failed = [r for r in results if _status(r.get("result")) >= 400]
            failed_id = failed[0].get("id") if failed else None
        else:
            for op in operations:
                if not isinstance(op, dict):
                    results.append({"action": None, "error": {"code": "invalid_operation", "message": "Operation must be an object"}, "status": 400})
                    failed_id = failed_id or str(len(results)-1)
                    continue
                deps = op.get("depends_on") or []
                if any(d not in completed for d in deps):
                    res = {"id": op.get("id"), "endpoint": _endpoint(op), "error": {"code": "dependency_failed", "message": f"Unmet dependency in {deps}"}, "status": 400}
                else:
                    res = await _run_one(op)
                results.append(res)
                st = _status(res.get("result", res))
                if st >= 400:
                    failed_id = op.get("id") or str(len(results)-1)
                    if stop_on_error or mode == "transaction":
                        break
                else:
                    completed.add(op.get("id") or str(len(results)-1))
        rollback_results = []
        if failed_id and rollback_on_error:
            for op in reversed(operations[:len(results)]):
                rb = op.get("rollback")
                if rb:
                    rollback_results.append(await _run_one({"id": f"rollback:{op.get('id')}", **rb}))
        ok = failed_id is None
        return {"ok": ok, "results": results, "failed_operation_id": failed_id, "rollback_results": rollback_results, "latency_ms": round((time.time()-start)*1000,2), "timestamp": int(time.time()*1000)}
    except Exception as e:
        return {"error": {"code": "internal_error", "message": str(e)}, "status": 500, "latency_ms": round((time.time()-start)*1000,2), "timestamp": int(time.time()*1000)}
