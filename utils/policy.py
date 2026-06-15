from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Iterable

from utils import eval_telemetry


DEFAULT_BLOCKED_PATTERNS = [
    ".env", "*.pem", "*.key", "id_rsa", "id_ed25519", ".ssh/*", ".aws/*",
    ".gcp/*", ".azure/*", ".config/openai/*", ".chatgpt_session*",
    "*session-token*", "*credentials*", "*.sqlite", "*.db",
]

EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", "coverage", ".next",
}


class PolicyError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def allowed_roots() -> list[Path]:
    configured = os.getenv("REPO_ALLOWED_ROOTS", "/root,/workspace,/tmp,/home/obsidian")
    return [Path(p).expanduser().resolve() for p in configured.split(",") if p.strip()]


def worktree_root() -> Path:
    return Path(os.getenv("WORKTREE_ROOT", "/tmp/gpt-api-worktrees")).expanduser().resolve()


def blocked_patterns() -> list[str]:
    configured = os.getenv("POLICY_BLOCKED_PATH_PATTERNS", "")
    extra = [p.strip() for p in configured.split(",") if p.strip()]
    return DEFAULT_BLOCKED_PATTERNS + extra


def resolve_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def ensure_under_allowed_root(path: str | Path) -> Path:
    resolved = resolve_path(path)
    roots = allowed_roots() + [worktree_root()]
    if not any(resolved == root or root in resolved.parents for root in roots):
        raise PolicyError("path_outside_allowed_roots", f"Path is outside allowed roots: {resolved}")
    return resolved


def ensure_relative_safe(rel_path: str | Path) -> Path:
    rel = Path(rel_path)
    if rel.is_absolute():
        raise PolicyError("absolute_path_forbidden", "Absolute paths are forbidden in patches and repo-relative operations.")
    if ".." in rel.parts:
        raise PolicyError("path_traversal_forbidden", "Path traversal is forbidden.")
    return rel


def is_blocked_relative(rel_path: str | Path) -> bool:
    rel = str(Path(rel_path).as_posix()).lstrip("/")
    parts = Path(rel).parts
    if any(part in EXCLUDED_DIRS for part in parts):
        return True
    for pattern in blocked_patterns():
        pattern = pattern.strip().lstrip("/")
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(Path(rel).name, pattern):
            return True
    return False


def ensure_not_blocked(path: str | Path, *, repo_root: str | Path | None = None) -> Path:
    resolved = ensure_under_allowed_root(path)
    rel: Path
    if repo_root:
        root = resolve_path(repo_root)
        try:
            rel = resolved.relative_to(root)
        except ValueError:
            raise PolicyError("path_outside_repo", f"Path is outside repository: {resolved}")
    else:
        rel = Path(resolved.name)
    if is_blocked_relative(rel):
        raise PolicyError("blocked_path", f"Path is blocked by policy: {rel.as_posix()}")
    return resolved


def ensure_repo_path(path: str | Path) -> Path:
    resolved = ensure_under_allowed_root(path)
    if not resolved.exists() or not resolved.is_dir():
        raise PolicyError("invalid_repo_path", f"Repository path does not exist or is not a directory: {resolved}")
    return resolved


def safe_walk(root: str | Path):
    root = ensure_repo_path(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS and not is_blocked_relative(Path(dirpath).relative_to(root) / d)]
        rel_dir = Path(dirpath).relative_to(root)
        for filename in filenames:
            rel = rel_dir / filename
            if is_blocked_relative(rel):
                continue
            yield Path(dirpath) / filename, rel


def policy_result_for_path(path: str, repo_root: str | None = None) -> dict:
    try:
        resolved = ensure_not_blocked(path, repo_root=repo_root)
        out = {"allowed": True, "path": str(resolved), "risk": "readonly"}
        eval_telemetry.log_event("policy_path_checked", path=path, repo_root=repo_root, allowed=True, risk="readonly")
        return out
    except PolicyError as exc:
        out = {"allowed": False, "error": {"code": exc.code, "message": exc.message}}
        eval_telemetry.log_event("policy_path_checked", path=path, repo_root=repo_root, allowed=False, error_code=exc.code)
        return out


def evaluate_action(action: str, workspace_path: str | None = None, changed_files: list[str] | None = None, tests_passed: bool | None = None, quality_passed: bool | None = None, user_approved_network_write: bool = False) -> dict:
    action = (action or "").strip().lower()
    changed_files = changed_files or []
    reasons = []
    allowed = True
    risk = "low"

    if action in {"create_pr", "push_branch", "comment_pr", "network_write"} and not user_approved_network_write:
        allowed = False
        reasons.append("Network-writing action requires explicit user approval.")
        risk = "high"
    if action in {"commit", "create_pr", "push_branch"}:
        if tests_passed is False:
            allowed = False
            reasons.append("Tests failed or were not marked as passed.")
        if quality_passed is False:
            reasons.append("Quality checks failed or were not marked as passed.")
            risk = "medium"
    for file in changed_files:
        rel = str(file)
        if is_blocked_relative(rel):
            allowed = False
            reasons.append(f"Blocked or secret-like path changed: {rel}")
            risk = "high"
        lower = rel.lower()
        if any(term in lower for term in ["auth", "security", "token", "secret", "password", "permission", "policy"]):
            reasons.append(f"Security-sensitive path requires review: {rel}")
            risk = "high"
        if lower.endswith(("requirements.txt", "package-lock.json", "poetry.lock", "pnpm-lock.yaml", "yarn.lock", "cargo.lock")):
            reasons.append(f"Dependency/lockfile change requires review: {rel}")
            if risk != "high":
                risk = "medium"
    if not reasons:
        reasons.append("No policy blockers detected.")
    out = {"allowed": allowed, "risk": risk, "reasons": reasons, "action": action}
    eval_telemetry.log_event("policy_evaluated", action=action, allowed=allowed, risk=risk, changed_files=changed_files, tests_passed=tests_passed, quality_passed=quality_passed, user_approved_network_write=user_approved_network_write)
    return out


def evaluate_action_deep(
    action: str,
    workspace_path: str | None = None,
    changed_files: list[str] | None = None,
    tests_passed: bool | None = None,
    quality_passed: bool | None = None,
    user_approved_network_write: bool = False,
    user_approved_sensitive: bool = False,
    user_approved_large_diff: bool = False,
    user_approved_deletions: bool = False,
    diff_line_count: int = 0,
) -> dict:
    result = evaluate_action(action, workspace_path, changed_files, tests_passed, quality_passed, user_approved_network_write)
    allowed = bool(result.get("allowed"))
    risk = result.get("risk", "low")
    reasons = list(result.get("reasons", []))
    changed_files = changed_files or []
    lockfiles = ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb", "bun.lock", "poetry.lock", "pdm.lock", "uv.lock", "Cargo.lock", "go.sum")
    generated_dirs = ("dist/", "build/", "coverage/", ".next/", "target/", "vendor/")
    binary_ext = (".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".gz", ".tar", ".sqlite", ".db", ".wasm")
    sensitive = False
    deletions = False
    for f in changed_files:
        rel = str(f)
        marker = rel[:2]
        path = rel[2:].strip() if marker in {"D ", "M ", "A ", "R "} else rel
        lower = path.lower()
        if marker == "D ":
            deletions = True
        if lower.endswith(tuple(x.lower() for x in lockfiles)):
            sensitive = True; reasons.append(f"Lockfile/dependency change requires approval: {path}")
        if any(lower.startswith(d) or f"/{d}" in lower for d in generated_dirs):
            reasons.append(f"Generated/build artifact change detected: {path}")
            sensitive = True
        if lower.endswith(binary_ext):
            allowed = False; risk = "high"; reasons.append(f"Binary/database artifact changes are blocked: {path}")
        if "migration" in lower or lower.startswith("migrations/"):
            sensitive = True; reasons.append(f"Migration change requires approval: {path}")
    if diff_line_count and diff_line_count > 2000 and not user_approved_large_diff:
        allowed = False; risk = "high"; reasons.append("Large diff requires explicit approval.")
    if deletions and not user_approved_deletions:
        allowed = False; risk = "high"; reasons.append("File deletions require explicit approval.")
    if sensitive and not user_approved_sensitive:
        allowed = False; risk = "high"; reasons.append("Sensitive/dependency/generated changes require explicit approval.")
    out = {"allowed": allowed, "risk": risk, "reasons": list(dict.fromkeys(reasons)), "action": (action or "").strip().lower()}
    eval_telemetry.log_event("policy_evaluated", action=out["action"], allowed=allowed, risk=risk, changed_files=changed_files, tests_passed=tests_passed, quality_passed=quality_passed, user_approved_network_write=user_approved_network_write, deep=True, diff_line_count=diff_line_count)
    return out
