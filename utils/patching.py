from __future__ import annotations

import re
import tempfile
from pathlib import Path

from utils.policy import PolicyError, ensure_relative_safe, ensure_under_allowed_root, is_blocked_relative
from utils.safe_subprocess import run_checked

_FILE_RE = re.compile(r"^(?:diff --git a/(.*?) b/(.*?)|--- a/(.*)|\+\+\+ b/(.*))$")


def touched_files(patch: str) -> list[str]:
    files: list[str] = []
    for line in patch.splitlines():
        m = _FILE_RE.match(line.strip())
        if not m:
            continue
        for val in m.groups():
            if val and val != "/dev/null":
                rel = ensure_relative_safe(val)
                if is_blocked_relative(rel):
                    raise PolicyError("blocked_patch_path", f"Patch touches blocked path: {rel.as_posix()}")
                if rel.as_posix() not in files:
                    files.append(rel.as_posix())
    return files


def _write_patch_file(patch: str) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8", suffix=".patch")
    tmp.write(patch); tmp.close()
    return tmp.name


def preview(workspace_path: str, patch: str) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    files = touched_files(patch)
    patch_file = _write_patch_file(patch)
    try:
        check = run_checked(["git", "apply", "--check", patch_file], workspace, timeout=30)
        stat = run_checked(["git", "apply", "--stat", patch_file], workspace, timeout=30)
        return {"applies": check["exit_code"] == 0, "files_touched": files, "risk": "safe_write", "preview": stat["stdout"] or check["stderr"], "stderr": check["stderr"]}
    finally:
        Path(patch_file).unlink(missing_ok=True)


def apply_patch(workspace_path: str, patch: str) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    prev = preview(str(workspace), patch)
    if not prev["applies"]:
        return {"applied": False, **prev}
    patch_file = _write_patch_file(patch)
    try:
        result = run_checked(["git", "apply", patch_file], workspace, timeout=30)
        return {"applied": result["exit_code"] == 0, "files_touched": prev["files_touched"], "stdout": result["stdout"], "stderr": result["stderr"], "exit_code": result["exit_code"]}
    finally:
        Path(patch_file).unlink(missing_ok=True)


def revert_patch(workspace_path: str, patch: str) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    patch_file = _write_patch_file(patch)
    try:
        result = run_checked(["git", "apply", "-R", patch_file], workspace, timeout=30)
        return {"reverted": result["exit_code"] == 0, "stdout": result["stdout"], "stderr": result["stderr"], "exit_code": result["exit_code"]}
    finally:
        Path(patch_file).unlink(missing_ok=True)


import hashlib
import json
import time
import uuid


def _patch_dir(workspace: Path) -> Path:
    d = workspace / ".gpt-api" / "patches"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _patch_record_path(workspace: Path, patch_id: str) -> Path:
    safe = "".join(ch for ch in patch_id if ch.isalnum() or ch in "._-")
    if not safe:
        raise PolicyError("invalid_patch_id", "Patch id is invalid.")
    return _patch_dir(workspace) / f"{safe}.json"


def apply_recorded(workspace_path: str, patch: str, task_id: str | None = None, label: str | None = None) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    patch_id = f"patch_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    prev = preview(str(workspace), patch)
    if not prev.get("applies"):
        record = {"patch_id": patch_id, "task_id": task_id, "label": label, "applied": False, "preview": prev, "created_at": int(time.time()*1000)}
        _patch_record_path(workspace, patch_id).write_text(json.dumps(record, indent=2), encoding="utf-8")
        return record
    result = apply_patch(str(workspace), patch)
    record = {
        "patch_id": patch_id,
        "task_id": task_id,
        "label": label,
        "sha256": hashlib.sha256(patch.encode("utf-8")).hexdigest(),
        "patch": patch,
        "files_touched": result.get("files_touched", prev.get("files_touched", [])),
        "applied": result.get("applied", False),
        "preview": prev,
        "result": result,
        "created_at": int(time.time()*1000),
    }
    _patch_record_path(workspace, patch_id).write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def history(workspace_path: str, task_id: str | None = None) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    items = []
    for p in sorted(_patch_dir(workspace).glob("*.json")):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if task_id and rec.get("task_id") != task_id:
            continue
        rec = {k: v for k, v in rec.items() if k != "patch"}
        items.append(rec)
    return {"workspace_path": str(workspace), "patches": items, "count": len(items)}


def revert_recorded(workspace_path: str, patch_id: str) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    path = _patch_record_path(workspace, patch_id)
    if not path.exists():
        raise PolicyError("patch_not_found", f"Patch record not found: {patch_id}")
    rec = json.loads(path.read_text(encoding="utf-8"))
    patch = rec.get("patch")
    if not patch:
        raise PolicyError("patch_body_missing", "Recorded patch body is unavailable.")
    result = revert_patch(str(workspace), patch)
    rec["revert_result"] = result
    rec["reverted_at"] = int(time.time()*1000)
    path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return {"patch_id": patch_id, **result}


def validate_risk(workspace_path: str, patch: str, max_files: int = 25, max_lines: int = 2000) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    files = touched_files(patch)
    line_count = len(patch.splitlines())
    risks = []
    allowed = True
    if len(files) > max_files:
        allowed = False
        risks.append({"risk": "too_many_files", "count": len(files), "limit": max_files})
    if line_count > max_lines:
        allowed = False
        risks.append({"risk": "patch_too_large", "lines": line_count, "limit": max_lines})
    for f in files:
        lower = f.lower()
        if lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".sqlite", ".db")):
            allowed = False
            risks.append({"risk": "binary_or_blocked_artifact", "file": f})
        if any(term in lower for term in ["auth", "security", "token", "secret", "password", "policy"]):
            risks.append({"risk": "security_sensitive_file", "file": f})
    return {"workspace_path": str(workspace), "allowed": allowed, "files_touched": files, "line_count": line_count, "risks": risks}
