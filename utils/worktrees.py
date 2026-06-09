from __future__ import annotations

import re
import shutil
from pathlib import Path

from utils.policy import PolicyError, ensure_repo_path, worktree_root, ensure_under_allowed_root
from utils.safe_subprocess import run_checked


def _slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower()).strip("-")
    return value[:80] or "coding-task"


def create_worktree(repo_path: str, task_id: str, base_branch: str | None = None) -> dict:
    repo = ensure_repo_path(repo_path)
    root = worktree_root(); root.mkdir(parents=True, exist_ok=True)
    slug = _slug(task_id)
    branch = f"agent/{slug}"
    workspace = root / slug
    n = 2
    while workspace.exists():
        workspace = root / f"{slug}-{n}"; n += 1
    status = run_checked(["git", "status", "--porcelain"], repo, timeout=20)
    if status["exit_code"] != 0:
        raise PolicyError("not_a_git_repo", "Workspace isolation requires a git repository.")
    args = ["git", "worktree", "add", "-b", branch, str(workspace)]
    if base_branch:
        args.append(base_branch)
    result = run_checked(args, repo, timeout=60)
    if result["exit_code"] != 0:
        # Retry with unique branch when branch already exists.
        branch = f"agent/{slug}-{n}"
        args = ["git", "worktree", "add", "-b", branch, str(workspace)]
        if base_branch: args.append(base_branch)
        result = run_checked(args, repo, timeout=60)
    if result["exit_code"] != 0:
        raise PolicyError("worktree_create_failed", result["stderr"] or result["stdout"])
    return {"workspace_id": workspace.name, "workspace_path": str(workspace), "branch": branch, "base_branch": base_branch}


def status(workspace_path: str) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    result = run_checked(["git", "status", "--porcelain", "--branch"], workspace, timeout=20)
    if result["exit_code"] != 0:
        raise PolicyError("workspace_status_failed", result["stderr"])
    lines = result["stdout"].splitlines()
    return {"workspace_path": str(workspace), "branch": lines[0].replace("## ", "") if lines else None, "dirty": len(lines) > 1, "changed_files": lines[1:]}


def diff(workspace_path: str, staged: bool = False) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    argv = ["git", "diff", "--staged"] if staged else ["git", "diff"]
    result = run_checked(argv, workspace, timeout=30)
    return {"workspace_path": str(workspace), "diff": result["stdout"], "exit_code": result["exit_code"]}


def destroy(workspace_path: str, force: bool = False, keep_branch: bool = True) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    st = status(str(workspace))
    if st["dirty"] and not force:
        raise PolicyError("dirty_workspace", "Workspace has uncommitted changes; set force=true to remove.")
    result = run_checked(["git", "worktree", "remove"] + (["--force"] if force else []) + [str(workspace)], workspace.parent, timeout=60)
    if result["exit_code"] != 0 and workspace.exists() and force:
        shutil.rmtree(workspace)
    return {"removed": not workspace.exists(), "kept_branch": keep_branch, "workspace_path": str(workspace)}
