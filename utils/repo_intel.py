from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path

from utils.policy import EXCLUDED_DIRS, ensure_not_blocked, ensure_repo_path, safe_walk, is_blocked_relative
from utils.safe_subprocess import run_checked
from utils import eval_telemetry


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
    quality_commands = discover_quality_commands(repo)
    tree = "\n".join(_rel_tree(repo, max_depth))
    out = {
        "repo_path": str(repo), "is_git_repo": is_git, "branch": branch, "dirty": dirty,
        "languages": languages, "frameworks": frameworks, "important_files": important,
        "tree": tree, "test_commands": tests,
        "quality_commands": quality_commands,
    }
    eval_telemetry.log_event("repo_overview_completed", repo_path=str(repo), is_git_repo=is_git, branch=branch, dirty=dirty, languages=languages, frameworks=frameworks, important_file_count=len(important), tree_line_count=len(tree.splitlines()), test_command_count=len(tests), quality_command_count=len(quality_commands))
    return out


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


def repo_instructions(repo_path: str, max_bytes: int = 120000) -> dict:
    repo = ensure_repo_path(repo_path)
    candidates = [
        ".github/copilot-instructions.md",
        "AGENTS.md",
        "CLAUDE.md",
        "README.md",
        "CONTRIBUTING.md",
    ]
    candidates.extend(str(p.relative_to(repo)) for p in sorted((repo / ".cursor" / "rules").glob("*")) if p.is_file()) if (repo / ".cursor" / "rules").exists() else None
    candidates.extend(str(p.relative_to(repo)) for p in sorted((repo / "docs").glob("*.md"))[:20]) if (repo / "docs").exists() else None
    out = []
    remaining = max_bytes
    for name in candidates:
        if remaining <= 0:
            break
        path = repo / name
        if not path.exists() or not path.is_file():
            continue
        try:
            path = ensure_not_blocked(path, repo_root=repo)
            data = path.read_bytes()[:remaining]
            text = data.decode("utf-8", errors="replace")
            out.append({"file": name, "content": text, "truncated": path.stat().st_size > len(data)})
            remaining -= len(data)
        except Exception:
            continue
    result = {"instructions": out}
    eval_telemetry.log_event("repo_instructions_completed", repo_path=str(repo), file_count=len(out), files=[item.get("file") for item in out])
    return result


def dependency_graph(repo_path: str) -> dict:
    repo = ensure_repo_path(repo_path)
    manifests = []
    for name in ["requirements.txt", "pyproject.toml", "package.json", "go.mod", "Cargo.toml", "pom.xml", "build.gradle", "build.gradle.kts"]:
        path = repo / name
        if path.exists():
            try:
                manifests.append({"file": name, "content_preview": path.read_text(encoding="utf-8", errors="replace")[:20000]})
            except Exception:
                manifests.append({"file": name, "content_preview": ""})
    imports = []
    for file_path, rel in safe_walk(repo):
        if rel.suffix != ".py":
            continue
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.append(node.module or "")
        imports.append({"file": rel.as_posix(), "imports": sorted(set(n for n in names if n))})
    return {"manifests": manifests, "python_imports": imports[:500]}


def test_map(repo_path: str) -> dict:
    repo = ensure_repo_path(repo_path)
    mappings = []
    for file_path, rel in safe_walk(repo):
        if rel.suffix != ".py" or not rel.name.startswith("test_"):
            continue
        target_name = rel.name.replace("test_", "")
        candidates = [p.as_posix() for _, p in safe_walk(repo) if p.name == target_name and "tests" not in p.parts]
        mappings.append({"test_file": rel.as_posix(), "candidate_source_files": candidates[:10]})
    return {"mappings": mappings}


def relevant_context(repo_path: str, task: str, diagnostics: list[dict] | None = None, max_files: int = 12) -> dict:
    repo = ensure_repo_path(repo_path)
    scores: dict[str, int] = {}
    reasons: dict[str, list[str]] = {}

    def add(rel: str, score: int, reason: str):
        if is_blocked_relative(rel):
            return
        scores[rel] = scores.get(rel, 0) + score
        reasons.setdefault(rel, []).append(reason)

    words = [w.lower() for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", task or "")]
    for file_path, rel in safe_walk(repo):
        rels = rel.as_posix()
        lower_name = rels.lower()
        if rels in {"README.md", "CONTRIBUTING.md", "pyproject.toml", "requirements.txt", "package.json", "pytest.ini"}:
            add(rels, 2, "important project file")
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace").lower()
        except Exception:
            continue
        for word in words[:50]:
            if word in lower_name:
                add(rels, 5, f"task term in path: {word}")
            elif word in text:
                add(rels, 1, f"task term in content: {word}")
    for item in diagnostics or []:
        f = item.get("file")
        if f:
            add(str(f), 10, "diagnostic file")
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:max_files]
    files = [{"file": f, "score": score, "reasons": reasons.get(f, [])[:5]} for f, score in ranked]
    eval_telemetry.log_event("repo_relevant_context_completed", repo_path=str(repo), task_preview=(task or "")[:200], suggested_count=len(files), suggested_files=[f["file"] for f in files])
    return {"files": files}


def _python_defs_and_calls(path: Path) -> tuple[list[dict], list[dict]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return [], []
    defs, calls = [], []
    scope = []
    class V(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            defs.append({"name": node.name, "type": "function", "line": node.lineno, "scope": ".".join(scope)})
            scope.append(node.name); self.generic_visit(node); scope.pop()
        def visit_AsyncFunctionDef(self, node):
            defs.append({"name": node.name, "type": "async_function", "line": node.lineno, "scope": ".".join(scope)})
            scope.append(node.name); self.generic_visit(node); scope.pop()
        def visit_ClassDef(self, node):
            defs.append({"name": node.name, "type": "class", "line": node.lineno, "scope": ".".join(scope)})
            scope.append(node.name); self.generic_visit(node); scope.pop()
        def visit_Call(self, node):
            name = None
            if isinstance(node.func, ast.Name): name = node.func.id
            elif isinstance(node.func, ast.Attribute): name = node.func.attr
            if name: calls.append({"name": name, "line": getattr(node, "lineno", None), "scope": ".".join(scope)})
            self.generic_visit(node)
    V().visit(tree)
    return defs, calls


def callgraph(repo_path: str, max_files: int = 500) -> dict:
    repo = ensure_repo_path(repo_path)
    definitions, calls, edges = {}, [], []
    py_files = [(p, rel) for p, rel in safe_walk(repo) if rel.suffix == ".py"][:max_files]
    for path, rel in py_files:
        defs, file_calls = _python_defs_and_calls(path)
        for d in defs:
            definitions.setdefault(d["name"], []).append({"file": rel.as_posix(), **d})
        for c in file_calls:
            calls.append({"file": rel.as_posix(), **c})
    for c in calls:
        for d in definitions.get(c["name"], [])[:10]:
            edges.append({"caller_file": c["file"], "caller_scope": c.get("scope"), "callee": c["name"], "callee_file": d["file"], "callee_line": d["line"]})
    return {"definitions": definitions, "calls": calls[:2000], "edges": edges[:2000]}


def references(repo_path: str, symbol: str, max_results: int = 100) -> dict:
    repo = ensure_repo_path(repo_path)
    if not symbol or not re.match(r"^[A-Za-z_][A-Za-z0-9_\.:-]{0,200}$", symbol):
        return {"results": [], "error": {"code": "invalid_symbol", "message": "Invalid symbol."}}
    pat = re.compile(rf"\b{re.escape(symbol.split('.')[-1])}\b")
    results = []
    for path, rel in safe_walk(repo):
        if rel.suffix.lower() not in {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".md", ".yaml", ".yml", ".toml"}:
            continue
        try: lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception: continue
        for i, line in enumerate(lines, 1):
            if pat.search(line):
                results.append({"file": rel.as_posix(), "line": i, "snippet": line.strip()[:300]})
                if len(results) >= max_results: return {"symbol": symbol, "results": results}
    return {"symbol": symbol, "results": results}


def route_map(repo_path: str) -> dict:
    repo = ensure_repo_path(repo_path)
    routes = []
    patterns = [
        re.compile(r"@(?:router|app)\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]+)"),
        re.compile(r"app\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]+)"),
        re.compile(r"(?:router|app)\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]+)"),
    ]
    for path, rel in safe_walk(repo):
        if rel.suffix.lower() not in {".py", ".js", ".ts", ".tsx"}: continue
        try: lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception: continue
        for i, line in enumerate(lines, 1):
            for pat in patterns:
                m = pat.search(line)
                if m:
                    routes.append({"file": rel.as_posix(), "line": i, "method": m.group(1).upper(), "path": m.group(2), "snippet": line.strip()})
    out = {"routes": routes[:1000], "count": len(routes)}
    eval_telemetry.log_event("repo_route_map_completed", repo_path=str(repo), route_count=len(routes))
    return out


def changed_context(repo_path: str, base_ref: str | None = None) -> dict:
    repo = ensure_repo_path(repo_path)
    argv = ["git", "diff", "--name-status"] if not base_ref else ["git", "diff", "--name-status", base_ref]
    result = run_checked(argv, repo, timeout=30)
    files = []
    for line in result.get("stdout", "").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2: files.append({"status": parts[0], "file": parts[-1]})
    return {"base_ref": base_ref, "files": files, "exit_code": result.get("exit_code"), "stderr": result.get("stderr")}


def recent_history_context(repo_path: str, query: str | None = None, max_commits: int = 20) -> dict:
    repo = ensure_repo_path(repo_path)
    args = ["git", "log", f"--max-count={max_commits}", "--name-status", "--pretty=format:%H%x09%an%x09%ad%x09%s", "--date=iso"]
    if query: args.extend(["--grep", query])
    result = run_checked(args, repo, timeout=30)
    commits = []
    current = None
    for line in result.get("stdout", "").splitlines():
        if "\t" in line and len(line.split("\t", 3)) == 4 and not line[0] in "AMDRC":
            h, author, date, subject = line.split("\t", 3)
            current = {"commit": h, "author": author, "date": date, "subject": subject, "files": []}
            commits.append(current)
        elif current and line.strip():
            parts = line.split("\t")
            if len(parts) >= 2: current["files"].append({"status": parts[0], "file": parts[-1]})
    return {"query": query, "commits": commits, "exit_code": result.get("exit_code"), "stderr": result.get("stderr")}


def symbol_references(repo_path: str, symbols: list[str], max_results_per_symbol: int = 50) -> dict:
    return {"symbols": [references(repo_path, s, max_results_per_symbol) for s in symbols[:50]]}
