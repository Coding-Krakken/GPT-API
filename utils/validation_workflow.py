from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from utils.policy import ensure_under_allowed_root

INTERACTIVE_PATTERNS = [
    re.compile(r"How would you like to configure ESLint\?", re.I),
    re.compile(r"Would you like to", re.I),
    re.compile(r"\?\s*$", re.M),
]

SENSITIVE_NAME_PATTERNS = ["upload", "download", "export", "csv", "route.ts", "auth", "middleware", "proxy"]
TYPE_PATTERNS = [
    (re.compile(r"\bas\s+any\b"), "as any", "Use unknown plus runtime narrowing, a narrow interface, or schema validation."),
    (re.compile(r"\bRecord\s*<\s*string\s*,\s*any\s*>"), "Record<string, any>", "Use a narrow domain type or Record<string, unknown> with normalization."),
    (re.compile(r":\s*any\b"), ": any", "Replace broad any with a narrow type, unknown, or a validated schema."),
    (re.compile(r"JSON\.parse\([^\n]+\)\s+as\s+"), "JSON.parse cast", "Parse as unknown, then validate or normalize the expected shape."),
]


def _run_git(repo: Path, args: list[str], timeout: int = 15) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, timeout=timeout)


def git_preflight(repo_path: str | Path) -> dict[str, Any]:
    repo = ensure_under_allowed_root(repo_path)
    root_cp = _run_git(repo, ["rev-parse", "--show-toplevel"])
    if root_cp.returncode != 0:
        return {
            "repoRoot": str(repo),
            "head": None,
            "branch": None,
            "isDirty": None,
            "modifiedFiles": [],
            "untrackedFiles": [],
            "scopeIsolationWarning": "Not a git repository; validation scope cannot be isolated to a commit.",
            "gitStatusShort": "",
        }
    repo_root = ensure_under_allowed_root(root_cp.stdout.strip())
    head = _run_git(repo_root, ["rev-parse", "HEAD"]).stdout.strip() or None
    branch = _run_git(repo_root, ["branch", "--show-current"]).stdout.strip() or None
    status = _run_git(repo_root, ["status", "--short"]).stdout
    modified: list[str] = []
    untracked: list[str] = []
    for line in status.splitlines():
        if not line:
            continue
        marker = line[:2]
        file_name = line[3:] if len(line) > 3 else line.strip()
        if marker == "??":
            untracked.append(file_name)
        else:
            modified.append(file_name)
    is_dirty = bool(modified or untracked)
    warning = "Working tree has uncommitted changes; validation is not isolated to committed HEAD." if is_dirty else None
    return {
        "repoRoot": str(repo_root),
        "head": head,
        "branch": branch,
        "isDirty": is_dirty,
        "modifiedFiles": modified,
        "untrackedFiles": untracked,
        "scopeIsolationWarning": warning,
        "gitStatusShort": status,
    }


def _contains_interactive_prompt(stdout: str, stderr: str) -> str | None:
    text = f"{stdout}\n{stderr}"
    for pat in INTERACTIVE_PATTERNS:
        if pat.search(text):
            if "configure ESLint" in text or "next lint" in text.lower():
                return "Next.js lint attempted interactive ESLint setup."
            return "Command emitted an interactive prompt and is not CI-safe."
    return None


def _recommendation(reason: str, command: str) -> str:
    if "ESLint" in reason or "lint" in command.lower():
        return "Configure ESLint and replace interactive/deprecated next lint with eslint . --max-warnings=0 in CI."
    return "Replace this with a deterministic non-interactive CI command or add the missing configuration."


def validation_result(name: str, command: str, status: str, exit_code: int | None, duration_ms: int, scope: str, summary: str, confidence: str, **extra: Any) -> dict[str, Any]:
    out = {
        "name": name,
        "command": command,
        "status": status,
        "exitCode": exit_code,
        "durationMs": duration_ms,
        "scope": scope,
        "summary": summary,
        "confidenceImpact": confidence,
    }
    out.update(extra)
    return out


def run_validation_command(
    *,
    name: str,
    argv: list[str],
    cwd: str | Path,
    timeout_seconds: int = 120,
    validation_mode: str | None = None,
    target_ref: str | None = None,
) -> dict[str, Any]:
    start = time.time()
    cwd_path = ensure_under_allowed_root(cwd)
    preflight = git_preflight(cwd_path)
    command = " ".join(argv)
    mode = validation_mode or "workspace"
    run_cwd = cwd_path
    temp_worktree: Path | None = None
    repo_root = Path(preflight["repoRoot"]) if preflight.get("repoRoot") else cwd_path
    try:
        relative_cwd = cwd_path.relative_to(repo_root)
    except ValueError:
        relative_cwd = Path(".")
    scope = "dirty-worktree" if preflight.get("isDirty") else "clean-head"

    if mode == "clean-worktree":
        if preflight.get("isDirty"):
            ref = target_ref or preflight.get("head")
            if not ref:
                return validation_result(name, command, "blocked", None, int((time.time()-start)*1000), "dirty-worktree", "Clean validation requested but no target ref is available.", "High", preflight=preflight)
            temp_worktree = Path(tempfile.mkdtemp(prefix="review-worktree-"))
            shutil.rmtree(temp_worktree, ignore_errors=True)
            add = _run_git(Path(preflight["repoRoot"]), ["worktree", "add", "--detach", str(temp_worktree), str(ref)], timeout=60)
            if add.returncode != 0:
                return validation_result(name, command, "blocked", add.returncode, int((time.time()-start)*1000), "dirty-worktree", "Clean validation requested but temporary worktree creation failed.", "High", stdout=add.stdout, stderr=add.stderr, preflight=preflight)
            run_cwd = temp_worktree / relative_cwd
            if not run_cwd.exists():
                return validation_result(name, command, "blocked", None, int((time.time()-start)*1000), "temp-worktree", "Clean validation target cwd does not exist in temporary worktree.", "High", reason="missing_temp_cwd", preflight=preflight)
            scope = "temp-worktree"
        else:
            scope = "clean-head"
    elif preflight.get("isDirty"):
        scope = "dirty-worktree"

    env = os.environ.copy()
    env.update({"CI": "1", "NEXT_TELEMETRY_DISABLED": "1"})
    try:
        cp = subprocess.run(argv, cwd=str(run_cwd), capture_output=True, text=True, timeout=timeout_seconds, shell=False, env=env)
        duration = int((time.time() - start) * 1000)
        reason = _contains_interactive_prompt(cp.stdout, cp.stderr)
        if reason:
            return validation_result(name, command, "blocked_interactive", cp.returncode, duration, scope, reason, "High", reason=reason, recommendation=_recommendation(reason, command), stdout_tail=cp.stdout[-4000:], stderr_tail=cp.stderr[-4000:], preflight=preflight)
        status = "passed" if cp.returncode == 0 else "failed"
        summary = "Command completed successfully." if cp.returncode == 0 else "Command completed with a non-zero exit code."
        return validation_result(name, command, status, cp.returncode, duration, scope, summary, "Medium" if scope == "dirty-worktree" else "High", stdout_tail=cp.stdout[-8000:], stderr_tail=cp.stderr[-8000:], preflight=preflight)
    except subprocess.TimeoutExpired as exc:
        return validation_result(name, command, "blocked", -1, int((time.time()-start)*1000), scope, "Command timed out before completion.", "High", reason="timeout", stdout_tail=(exc.stdout or "")[-4000:], stderr_tail=(exc.stderr or "")[-4000:], preflight=preflight)
    except FileNotFoundError as exc:
        return validation_result(name, command, "blocked", 127, int((time.time()-start)*1000), scope, "Command executable was not found.", "High", reason="missing_executable", recommendation="Install the missing tool or choose a configured project script.", stdout_tail="", stderr_tail=str(exc), preflight=preflight)
    finally:
        if temp_worktree is not None:
            _run_git(Path(preflight["repoRoot"]), ["worktree", "remove", "--force", str(temp_worktree)], timeout=60)


def discover_suggested_checks(repo_path: str | Path) -> dict[str, Any]:
    repo = ensure_under_allowed_root(repo_path)
    available: list[str] = []
    interactive: list[str] = []
    missing_ci_safe_lint = False
    pkg_paths = [repo / "package.json", *sorted(repo.glob("apps/*/package.json")), *sorted(repo.glob("packages/*/package.json"))]
    for pkg in pkg_paths:
        if not pkg.exists():
            continue
        rel_dir = pkg.parent.relative_to(repo)
        workspace = None if rel_dir == Path(".") else "@" + "/".join(rel_dir.parts) if len(rel_dir.parts) >= 2 else str(rel_dir)
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except Exception:
            continue
        package_name = data.get("name") or workspace
        scripts = data.get("scripts") or {}
        suffix = f" --workspace={package_name}" if package_name and pkg.parent != repo else ""
        for script in ["type-check", "typecheck", "test", "build", "test:coverage"]:
            if script in scripts:
                available.append(f"npm run {script}{suffix}")
        if "lint" in scripts:
            cmd = f"npm run lint{suffix}"
            lint_body = str(scripts.get("lint", ""))
            if "next lint" in lint_body and not any((repo / name).exists() for name in ["eslint.config.js", "eslint.config.mjs", ".eslintrc", ".eslintrc.json", ".eslintrc.js"]):
                interactive.append(cmd)
                missing_ci_safe_lint = True
            else:
                available.append(cmd)
    if (repo / "pytest.ini").exists() or (repo / "pyproject.toml").exists() or (repo / "tests").exists():
        available.append("python -m pytest")
    if (repo / "tsconfig.json").exists():
        available.append("npx tsc --noEmit")
    return {"availableChecks": list(dict.fromkeys(available)), "possiblyInteractiveChecks": list(dict.fromkeys(interactive)), "missingCiSafeLint": missing_ci_safe_lint}


def _changed_files(repo: Path) -> list[str]:
    cp = _run_git(repo, ["diff", "--name-only", "HEAD"])
    files = cp.stdout.splitlines() if cp.returncode == 0 else []
    status = git_preflight(repo)
    files.extend(status.get("untrackedFiles") or [])
    return list(dict.fromkeys(f for f in files if f))


def security_review(repo_path: str | Path, changed_files: list[str] | None = None) -> dict[str, Any]:
    repo = ensure_under_allowed_root(repo_path)
    files = changed_files or _changed_files(repo)
    triggers: set[str] = set()
    for rel in files:
        lower = rel.lower()
        if any(pat in lower for pat in SENSITIVE_NAME_PATTERNS):
            triggers.add("filename:" + rel)
        path = repo / rel
        if path.exists() and path.is_file() and path.suffix.lower() in {".ts", ".tsx", ".js", ".jsx", ".py"}:
            text = path.read_text(encoding="utf-8", errors="replace")[:200000]
            if "JSON.parse" in text: triggers.add("JSON.parse")
            if re.search(r"\bfetch\s*\(", text): triggers.add("fetch")
            if re.search(r"from ['\"]fs|require\(['\"]fs|\bfs\.", text): triggers.add("fs")
            if "prisma" in text: triggers.add("prisma")
            if re.search(r"csv|CSV", text): triggers.add("CSV export")
    checklist = []
    if triggers:
        checklist = ["path traversal", "CSV/formula injection", "SSRF/proxy validation", "auth/authz", "unsafe JSON parsing", "data leakage", "secret exposure", "insecure defaults"]
    return {"securityReviewRequired": bool(triggers), "triggers": sorted(triggers), "checklist": checklist}


def type_safety_warnings(repo_path: str | Path, changed_files: list[str] | None = None) -> dict[str, Any]:
    repo = ensure_under_allowed_root(repo_path)
    files = changed_files or _changed_files(repo)
    warnings: list[dict[str, Any]] = []
    for rel in files:
        if not rel.endswith((".ts", ".tsx")):
            continue
        path = repo / rel
        if not path.exists() or not path.is_file():
            continue
        for idx, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            for pattern, label, recommendation in TYPE_PATTERNS:
                if pattern.search(line):
                    warnings.append({"file": rel, "line": idx, "pattern": label, "recommendation": recommendation})
    return {"typeSafetyWarnings": warnings[:100]}
