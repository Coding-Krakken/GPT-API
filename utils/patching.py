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
