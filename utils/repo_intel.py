from __future__ import annotations

import ast
import json
import os
from pathlib import Path

from utils.policy import EXCLUDED_DIRS, ensure_not_blocked, ensure_repo_path, safe_walk
from utils.safe_subprocess import run_checked


def _rel_tree(repo: Path, max_depth: int) -> list[str]:
    lines: list[str] = []
    for dirpath, dirnames, filenames in os.walk(repo):
        rel_dir = Path(dirpath).relative_to(repo)
        depth = 0 if str(rel_dir) == "." else len(rel_dir.parts)
        if depth >= max_depth:
            dirnames[:] = []
        dirnames[:] = [d for d in sorted(dirnames) if d not in EXCLUDED_DIRS]
        filenames = sorted(f for f in filenames if not f.endswith((".pyc", ".pyo")))
        indent = "  " * depth
        if rel_dir != Path("."):
            lines.append(f"{indent}{rel_dir.name}/")
        if depth < max_depth:
            for f in filenames[:80]:
                lines.append(f"{indent}  {f}")
    return lines[:1000]


def detect_project(repo: Path) -> tuple[list[str], list[str], list[str], list[str]]:
    languages: set[str] = set()
    frameworks: set[str] = set()
    important: list[str] = []
    tests: list[str] = []
    files = {p.name for p in repo.iterdir() if p.exists()}
    for file_path, rel in safe_walk(repo):
        suffix = file_path.suffix.lower()
        if suffix == ".py": languages.add("python")
        elif suffix in {".js", ".jsx"}: languages.add("javascript")
        elif suffix in {".ts", ".tsx"}: languages.add("typescript")
        elif suffix == ".go": languages.add("go")
        elif suffix == ".rs": languages.add("rust")
        if rel.as_posix() in {"pyproject.toml", "requirements.txt", "package.json", "go.mod", "Cargo.toml", "pytest.ini", "main.py"}:
            important.append(rel.as_posix())
    if "pytest.ini" in files or (repo / "tests").exists():
        frameworks.add("pytest"); tests.append("python -m pytest")
    if "requirements.txt" in files or "pyproject.toml" in files:
        frameworks.add("python")
    pkg = repo / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            scripts = data.get("scripts", {})
            if "test" in scripts: tests.append("npm test")
            if "lint" in scripts: tests.append("npm run lint")
        except Exception:
            pass
    if "go.mod" in files: tests.append("go test ./...")
    if "Cargo.toml" in files: tests.append("cargo test")
    return sorted(languages), sorted(frameworks), sorted(set(important)), tests


def overview(repo_path: str, max_depth: int = 4) -> dict:
    repo = ensure_repo_path(repo_path)
    git_status = run_checked(["git", "status", "--porcelain", "--branch"], repo, timeout=15)
    branch = None; dirty = None; is_git = (repo / ".git").exists()
    if git_status["exit_code"] == 0:
        lines = git_status["stdout"].splitlines()
        branch = lines[0].replace("## ", "") if lines else None
        dirty = len(lines) > 1
        is_git = True
    languages, frameworks, important, tests = detect_project(repo)
    return {
        "repo_path": str(repo), "is_git_repo": is_git, "branch": branch, "dirty": dirty,
        "languages": languages, "frameworks": frameworks, "important_files": important,
        "tree": "\n".join(_rel_tree(repo, max_depth)), "test_commands": tests,
        "quality_commands": discover_quality_commands(repo),
    }


def search(repo_path: str, query: str, globs: list[str] | None = None, max_results: int = 50) -> dict:
    repo = ensure_repo_path(repo_path)
    if not query:
        return {"results": []}
    results = []
    for file_path, rel in safe_walk(repo):
        if globs and not any(rel.match(g) for g in globs):
            continue
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for idx, line in enumerate(text.splitlines(), start=1):
            col = line.find(query)
            if col >= 0:
                results.append({"file": rel.as_posix(), "line": idx, "column": col + 1, "snippet": line.strip()[:300]})
                if len(results) >= max_results:
                    return {"results": results}
    return {"results": results}


def read_context(repo_path: str, files: list[str], max_bytes_per_file: int = 50000) -> dict:
    repo = ensure_repo_path(repo_path)
    out = []
    for name in files:
        rel = Path(name)
        target = ensure_not_blocked(repo / rel, repo_root=repo)
        data = target.read_bytes()[:max_bytes_per_file]
        out.append({"file": rel.as_posix(), "content": data.decode("utf-8", errors="replace"), "truncated": target.stat().st_size > max_bytes_per_file})
    return {"files": out}


def symbols(repo_path: str, files: list[str] | None = None) -> dict:
    repo = ensure_repo_path(repo_path)
    selected = [Path(f) for f in files] if files else [rel for p, rel in safe_walk(repo) if rel.suffix == ".py"]
    output = []
    for rel in selected[:200]:
        if rel.suffix != ".py":
            continue
        path = ensure_not_blocked(repo / rel, repo_root=repo)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        entries = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                entries.append({"name": node.name, "type": type(node).__name__, "line": node.lineno})
        output.append({"file": rel.as_posix(), "symbols": entries})
    return {"files": output}


def discover_quality_commands(repo: Path) -> list[str]:
    cmds = []
    if (repo / "pyproject.toml").exists() or (repo / "requirements.txt").exists() or (repo / "pytest.ini").exists():
        cmds.extend(["python -m pytest", "python -m compileall ."])
    if (repo / "package.json").exists():
        try:
            scripts = json.loads((repo / "package.json").read_text()).get("scripts", {})
            for name in ("lint", "typecheck", "test"):
                if name in scripts:
                    cmds.append(f"npm run {name}")
        except Exception:
            pass
    if (repo / "go.mod").exists(): cmds.append("go test ./...")
    if (repo / "Cargo.toml").exists(): cmds.append("cargo test")
    return list(dict.fromkeys(cmds))
