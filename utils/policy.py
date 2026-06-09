from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Iterable


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
        return {"allowed": True, "path": str(resolved), "risk": "readonly"}
    except PolicyError as exc:
        return {"allowed": False, "error": {"code": exc.code, "message": exc.message}}
