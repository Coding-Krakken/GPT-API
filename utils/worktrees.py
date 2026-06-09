from __future__ import annotations

import re
import shutil
from pathlib import Path

from utils.policy import PolicyError, ensure_repo_path, worktree_root, ensure_under_allowed_root
from utils.safe_subprocess import run_checked
from utils import eval_telemetry


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
    out = {"workspace_id": workspace.name, "workspace_path": str(workspace), "branch": branch, "base_branch": base_branch}
    eval_telemetry.log_event("workspace_created", repo_path=str(repo), workspace_path=str(workspace), branch=branch, base_branch=base_branch)
    return out


def status(workspace_path: str) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    result = run_checked(["git", "status", "--porcelain", "--branch"], workspace, timeout=20)
    if result["exit_code"] != 0:
        raise PolicyError("workspace_status_failed", result["stderr"])
    lines = result["stdout"].splitlines()
    out = {"workspace_path": str(workspace), "branch": lines[0].replace("## ", "") if lines else None, "dirty": len(lines) > 1, "changed_files": lines[1:]}
    eval_telemetry.log_event("workspace_status_checked", workspace_path=str(workspace), branch=out["branch"], dirty=out["dirty"], changed_count=len(out["changed_files"]))
    return out


def diff(workspace_path: str, staged: bool = False) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    argv = ["git", "diff", "--staged"] if staged else ["git", "diff"]
    result = run_checked(argv, workspace, timeout=30)
    out = {"workspace_path": str(workspace), "diff": result["stdout"], "exit_code": result["exit_code"]}
    eval_telemetry.log_event("workspace_diff_checked", workspace_path=str(workspace), staged=staged, exit_code=result["exit_code"], diff_chars=len(result["stdout"]))
    return out


def destroy(workspace_path: str, force: bool = False, keep_branch: bool = True) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    st = status(str(workspace))
    if st["dirty"] and not force:
        raise PolicyError("dirty_workspace", "Workspace has uncommitted changes; set force=true to remove.")
    result = run_checked(["git", "worktree", "remove"] + (["--force"] if force else []) + [str(workspace)], workspace.parent, timeout=60)
    if result["exit_code"] != 0 and workspace.exists() and force:
        shutil.rmtree(workspace)
    out = {"removed": not workspace.exists(), "kept_branch": keep_branch, "workspace_path": str(workspace)}
    eval_telemetry.log_event("workspace_destroyed", workspace_path=str(workspace), removed=out["removed"], force=force, keep_branch=keep_branch)
    return out


def commit(workspace_path: str, message: str, files: list[str] | None = None) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    if not message or len(message.strip()) < 3:
        raise PolicyError("invalid_commit_message", "Commit message must be at least 3 characters.")
    if files:
        for rel in files:
            if rel.startswith("/") or ".." in Path(rel).parts:
                raise PolicyError("invalid_commit_path", f"Invalid commit path: {rel}")
            add = run_checked(["git", "add", "--", rel], workspace, timeout=30)
            if add["exit_code"] != 0:
                raise PolicyError("git_add_failed", add["stderr"] or add["stdout"])
    else:
        add = run_checked(["git", "add", "--all"], workspace, timeout=30)
        if add["exit_code"] != 0:
            raise PolicyError("git_add_failed", add["stderr"] or add["stdout"])
        # Internal task/patch metadata is for the agent ledger and must not be committed.
        run_checked(["git", "reset", "--", ".gpt-api"], workspace, timeout=30)
    result = run_checked(["git", "commit", "-m", message.strip()], workspace, timeout=60)
    if result["exit_code"] != 0:
        raise PolicyError("git_commit_failed", result["stderr"] or result["stdout"])
    rev = run_checked(["git", "rev-parse", "--short", "HEAD"], workspace, timeout=10)
    out = {"committed": True, "commit": rev["stdout"].strip(), "stdout": result["stdout"], "stderr": result["stderr"]}
    eval_telemetry.log_event("workspace_committed", workspace_path=str(workspace), commit=out["commit"], files=files)
    return out


def pr_create(workspace_path: str, title: str, body: str, dry_run: bool = True) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    if not title or len(title.strip()) < 3:
        raise PolicyError("invalid_pr_title", "PR title must be at least 3 characters.")
    argv = ["gh", "pr", "create", "--title", title.strip(), "--body", body or ""]
    if dry_run:
        eval_telemetry.log_event("pr_dry_run_created", workspace_path=str(workspace), title=title.strip())
        return {"dry_run": True, "argv": argv, "workspace_path": str(workspace)}
    result = run_checked(argv, workspace, timeout=120)
    if result["exit_code"] != 0:
        raise PolicyError("pr_create_failed", result["stderr"] or result["stdout"])
    out = {"created": True, "url": result["stdout"].strip(), "stderr": result["stderr"]}
    eval_telemetry.log_event("pr_created", workspace_path=str(workspace), url=out["url"])
    return out


def diff_summary(workspace_path: str) -> dict:
    workspace = ensure_under_allowed_root(workspace_path)
    raw = run_checked(["git", "diff", "--stat"], workspace, timeout=30)
    names = run_checked(["git", "diff", "--name-status"], workspace, timeout=30)
    full = run_checked(["git", "diff", "--numstat"], workspace, timeout=30)
    files = []
    for line in names["stdout"].splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            files.append({"status": parts[0], "file": parts[-1]})
    out = {"workspace_path": str(workspace), "stat": raw["stdout"], "files": files, "numstat": full["stdout"]}
    eval_telemetry.log_event("workspace_diff_summary", workspace_path=str(workspace), changed_count=len(files))
    return out


def risk_report(workspace_path: str) -> dict:
    summary = diff_summary(workspace_path)
    risks = []
    sensitive_terms = ["auth", "security", "token", "secret", "password", "permission", "policy", "admin", "sudo"]
    for item in summary.get("files", []):
        path = item["file"].lower()
        if any(term in path for term in sensitive_terms):
            risks.append({"file": item["file"], "risk": "security_sensitive_path", "severity": "high"})
        if path.endswith(("requirements.txt", "package-lock.json", "poetry.lock", "pnpm-lock.yaml", "yarn.lock", "cargo.lock")):
            risks.append({"file": item["file"], "risk": "dependency_or_lockfile_change", "severity": "medium"})
        if item.get("status", "").startswith("D"):
            risks.append({"file": item["file"], "risk": "file_deleted", "severity": "medium"})
    return {"workspace_path": summary["workspace_path"], "risks": risks, "risk_count": len(risks)}


def review_checklist(workspace_path: str) -> dict:
    summary = diff_summary(workspace_path)
    risk = risk_report(workspace_path)
    checklist = [
        {"item": "Changes are isolated to a worktree", "status": "pass"},
        {"item": "Review raw diff before commit", "status": "required"},
        {"item": "Run focused tests", "status": "required"},
        {"item": "Run quality checks when available", "status": "required"},
        {"item": "Document residual risks", "status": "required"},
    ]
    if risk["risk_count"]:
        checklist.append({"item": "Security/dependency-sensitive changes need explicit review", "status": "required"})
    return {"workspace_path": summary["workspace_path"], "changed_files": summary["files"], "risks": risk["risks"], "checklist": checklist}
