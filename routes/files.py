from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional, Any
import os
import shutil
import time
import hashlib
import glob as globlib
import difflib
from pathlib import Path
from utils.auth import verify_key
from utils.operation_policy import block_if_confirmation_required, confirmation_present, error_payload, file_danger_reasons

router = APIRouter()


class FileRange(BaseModel):
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    start_column: Optional[int] = None
    end_column: Optional[int] = None


class FileOp(BaseModel):
    action: str
    path: str
    target_path: Optional[str] = None
    content: Optional[str] = None
    patch: Optional[str] = None
    range: Optional[FileRange] = None
    fault: Optional[str] = None
    recursive: bool = False
    encoding: str = "utf-8"
    create: bool = False
    overwrite: bool = True
    backup: bool = False
    expected_hash: Optional[str] = None
    confirm: bool = False
    confirmation: Optional[str] = None
    glob: Optional[str] = None
    include_hidden: bool = False
    max_depth: Optional[int] = None
    limit: int = 10000


class FileRequest(BaseModel):
    action: Optional[str] = None
    path: Optional[str] = None
    target_path: Optional[str] = None
    content: Optional[str] = None
    patch: Optional[str] = None
    range: Optional[FileRange] = None
    fault: Optional[str] = None
    recursive: bool = False
    encoding: str = "utf-8"
    create: bool = False
    overwrite: bool = True
    backup: bool = False
    expected_hash: Optional[str] = None
    confirm: bool = False
    confirmation: Optional[str] = None
    glob: Optional[str] = None
    include_hidden: bool = False
    max_depth: Optional[int] = None
    limit: int = 10000
    operations: Optional[List[FileOp]] = None


def _abs(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _backup(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    backup_path = f"{path}.bak.{int(time.time() * 1000)}"
    if os.path.isdir(path):
        shutil.copytree(path, backup_path)
    else:
        shutil.copy2(path, backup_path)
    return backup_path


def _check_hash(path: str, expected: Optional[str]):
    if expected and os.path.exists(path):
        actual = _sha256(path)
        if actual != expected:
            return {"error": {"code": "hash_mismatch", "message": f"Expected SHA256 {expected}, got {actual}"}, "status": 409, "sha256": actual}
    return None


def _read(path: str, encoding: str) -> str:
    with open(path, "r", encoding=encoding) as f:
        return f.read()


def _write(path: str, content: str, encoding: str):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding=encoding) as f:
        f.write(content)


def _line_edit(text: str, op: FileOp) -> str:
    lines = text.splitlines(keepends=True)
    r = op.range or FileRange()
    if r.start_line is None:
        raise ValueError("range.start_line is required")
    start = max(r.start_line - 1, 0)
    end = max((r.end_line or r.start_line) - 1, start)
    content = op.content or ""
    if op.action == "replace_range":
        return "".join(lines[:start] + [content] + lines[end + 1:])
    if op.action == "delete_range":
        return "".join(lines[:start] + lines[end + 1:])
    if op.action == "insert_before":
        return "".join(lines[:start] + [content] + lines[start:])
    if op.action == "insert_after":
        insert_at = end + 1
        return "".join(lines[:insert_at] + [content] + lines[insert_at:])
    raise ValueError(f"unsupported range edit: {op.action}")


def _apply_unified_patch(path: str, original: str, patch_text: str) -> str:
    # Lightweight single-file unified patch applier. Falls back to external patch if needed.
    import tempfile
    if not patch_text:
        return original
    try:
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as pf:
            pf.write(patch_text)
            patch_file = pf.name
        import subprocess
        proc = subprocess.run(["patch", path, patch_file], capture_output=True, text=True, timeout=60)
        os.unlink(patch_file)
        if proc.returncode == 0:
            return _read(path, "utf-8")
        raise RuntimeError(proc.stderr or proc.stdout)
    except FileNotFoundError:
        raise RuntimeError("External 'patch' command is required for unified patch application")


def _tree(root: str, include_hidden: bool, max_depth: Optional[int], limit: int):
    items = []
    base_depth = root.rstrip(os.sep).count(os.sep)
    for cur, dirs, files in os.walk(root):
        depth = cur.rstrip(os.sep).count(os.sep) - base_depth
        if max_depth is not None and depth >= max_depth:
            dirs[:] = []
        if not include_hidden:
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            files = [f for f in files if not f.startswith(".")]
        for name in dirs + files:
            p = os.path.join(cur, name)
            items.append({"path": p, "relative_path": os.path.relpath(p, root), "type": "directory" if os.path.isdir(p) else "file"})
            if len(items) >= limit:
                return items
    return items


def _do_file_op(op: FileOp):
    if not op.action or not op.path:
        return {"error": {"code": "missing_field", "message": "Missing required field: action or path"}, "status": 400}
    if op.fault == "permission":
        return {"error": {"code": "permission_denied", "message": "Permission denied"}, "status": 403}
    if op.fault == "io":
        return {"error": {"code": "io_error", "message": "I/O error occurred"}, "status": 500}
    path = _abs(op.path)
    target = _abs(op.target_path) if op.target_path else None
    try:
        action = op.action
        if action == "exists":
            return {"exists": os.path.exists(path), "status": 200}
        if action == "mkdir":
            os.makedirs(path, exist_ok=True)
            return {"status": 200, "message": f"Directory created: {path}"}
        if action == "glob":
            pattern = op.glob or path
            matches = globlib.glob(_abs(pattern), recursive=op.recursive)
            if not op.include_hidden:
                matches = [m for m in matches if not any(part.startswith('.') for part in Path(m).parts)]
            return {"matches": matches[:op.limit], "count": min(len(matches), op.limit), "status": 200}
        if not os.path.exists(path) and action not in ["write", "append", "prepend", "snapshot", "restore"]:
            if action == "list":
                return {"error": {"code": "not_a_directory", "message": "Path is not a directory."}, "status": 400}
            return {"error": {"code": "not_found", "message": f"Path '{path}' does not exist."}, "status": 404}
        if action == "read":
            content = _read(path, op.encoding)
            return {"content": content, "sha256": _sha256(path), "status": 200}
        if action == "stat":
            st = os.stat(path)
            return {"size": st.st_size, "mtime": st.st_mtime, "ctime": st.st_ctime, "is_dir": os.path.isdir(path), "sha256": None if os.path.isdir(path) else _sha256(path), "status": 200}
        if action == "checksum":
            if os.path.isdir(path):
                return {"error": {"code": "is_directory", "message": "checksum requires a file path"}, "status": 400}
            return {"sha256": _sha256(path), "status": 200}
        if action == "list":
            if not os.path.isdir(path):
                return {"error": {"code": "not_a_directory", "message": "Path is not a directory."}, "status": 400}
            items = os.listdir(path)
            if not op.include_hidden:
                items = [x for x in items if not x.startswith(".")]
            return {"items": items[:op.limit], "count": min(len(items), op.limit), "status": 200}
        if action == "tree":
            if not os.path.isdir(path):
                return {"error": {"code": "not_a_directory", "message": "Path is not a directory."}, "status": 400}
            return {"items": _tree(path, op.include_hidden, op.max_depth, op.limit), "status": 200}
        target_exists = bool(target and os.path.exists(target))
        reasons = file_danger_reasons(action, recursive=op.recursive, overwrite_target_exists=target_exists)
        decision = block_if_confirmation_required(area="files", operation=action, reasons=reasons, confirmed=confirmation_present(op.confirmation, explicit_confirm=op.confirm))
        if not decision.allowed:
            return error_payload(decision)
        if action in ["write", "append", "prepend", "replace_range", "insert_before", "insert_after", "delete_range", "patch"]:
            if os.path.exists(path) and not op.overwrite and action == "write":
                return {"error": {"code": "exists", "message": "File exists and overwrite=false"}, "status": 409}
            if not os.path.exists(path) and not op.create and action != "write":
                return {"error": {"code": "not_found", "message": "File does not exist; set create=true if creation is intended."}, "status": 404}
            hash_err = _check_hash(path, op.expected_hash)
            if hash_err:
                return hash_err
            backup_path = _backup(path) if op.backup else None
            old = _read(path, op.encoding) if os.path.exists(path) else ""
            if action == "write":
                new = op.content or ""
            elif action == "append":
                new = old + (op.content or "")
            elif action == "prepend":
                new = (op.content or "") + old
            elif action in ["replace_range", "insert_before", "insert_after", "delete_range"]:
                new = _line_edit(old, op)
            elif action == "patch":
                if op.patch and op.patch.lstrip().startswith(("---", "diff ")):
                    if op.backup and backup_path:
                        pass
                    new = _apply_unified_patch(path, old, op.patch)
                    return {"status": 200, "message": f"Patched {path}", "sha256": _sha256(path), "backup_path": backup_path}
                else:
                    new = (op.patch if op.patch is not None else op.content) or old
            diff = "\n".join(difflib.unified_diff(old.splitlines(), new.splitlines(), fromfile=path, tofile=path, lineterm=""))
            _write(path, new, op.encoding)
            return {"status": 200, "message": f"{action} completed for {path}", "sha256": _sha256(path), "backup_path": backup_path, "diff": diff}
        if action == "delete":
            backup_path = _backup(path) if op.backup else None
            if os.path.isdir(path):
                if not op.recursive:
                    return {"error": {"code": "is_directory", "message": "Directory delete requires recursive=true"}, "status": 400}
                shutil.rmtree(path)
            else:
                os.remove(path)
            return {"status": 200, "message": f"Deleted {path}", "backup_path": backup_path}
        if action == "copy":
            if not target:
                return {"error": {"code": "missing_target", "message": "target_path required for copy"}, "status": 400}
            if os.path.isdir(path):
                shutil.copytree(path, target, dirs_exist_ok=op.overwrite)
            else:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copy2(path, target)
            return {"status": 200, "message": f"Copied {path} to {target}"}
        if action == "move":
            if not target:
                return {"error": {"code": "missing_target", "message": "target_path required for move"}, "status": 400}
            shutil.move(path, target)
            return {"status": 200, "message": f"Moved {path} to {target}"}
        if action == "snapshot":
            snap = target or f"{path}.snapshot.{int(time.time() * 1000)}"
            if os.path.isdir(path):
                shutil.copytree(path, snap, dirs_exist_ok=True)
            else:
                os.makedirs(os.path.dirname(snap), exist_ok=True)
                shutil.copy2(path, snap)
            return {"status": 200, "snapshot_path": snap}
        if action == "restore":
            if not target:
                return {"error": {"code": "missing_target", "message": "target_path is the restore destination"}, "status": 400}
            if os.path.isdir(path):
                if os.path.exists(target):
                    shutil.rmtree(target)
                shutil.copytree(path, target)
            else:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copy2(path, target)
            return {"status": 200, "message": f"Restored {path} to {target}"}
        return {"error": {"code": "unsupported_action", "message": f"Unsupported action: {action}"}, "status": 400}
    except Exception as e:
        return {"error": {"code": "internal_error", "message": str(e)}, "status": 500}


@router.post("", dependencies=[Depends(verify_key)])
@router.post("/", dependencies=[Depends(verify_key)])
def handle_file_operation(req: FileRequest):
    start = time.time()
    try:
        if req.operations:
            results = [_do_file_op(op) for op in req.operations]
            return {"results": results, "latency_ms": round((time.time() - start) * 1000, 2), "timestamp": int(time.time() * 1000)}
        if not req.action or not req.path:
            return {"error": {"code": "missing_field", "message": "Missing required field: action or path"}, "status": 400}
        op = FileOp(**req.model_dump(exclude={"operations"}))
        result = _do_file_op(op)
        return {"result": result, "latency_ms": round((time.time() - start) * 1000, 2), "timestamp": int(time.time() * 1000)}
    except Exception as e:
        return {"error": {"code": "internal_error", "message": str(e)}, "status": 500, "latency_ms": round((time.time() - start) * 1000, 2), "timestamp": int(time.time() * 1000)}
