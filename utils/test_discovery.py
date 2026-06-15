from __future__ import annotations

import json
import re
from pathlib import Path

from utils.policy import ensure_under_allowed_root
from utils.safe_subprocess import run_checked
from utils import eval_telemetry
from utils.validation_workflow import git_preflight, run_validation_command


def discover(workspace_path: str) -> dict:
    root = ensure_under_allowed_root(workspace_path)
    commands: list[dict] = []
    frameworks: set[str] = set()
    if (root / "pytest.ini").exists() or (root / "tests").exists() or (root / "pyproject.toml").exists():
        frameworks.add("pytest")
        commands.append({"name": "pytest", "argv": ["python", "-m", "pytest"], "scope": "all"})
        tests_dir = root / "tests"
        if tests_dir.exists():
            for test_file in sorted(tests_dir.rglob("test_*.py"))[:20]:
                commands.append({"name": f"pytest {test_file.relative_to(root)}", "argv": ["python", "-m", "pytest", str(test_file.relative_to(root))], "scope": "focused"})
    def add_node_scripts(pkg: Path, prefix: str = ""):
        try:
            scripts = json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {})
            cwd = str(pkg.parent.relative_to(root)) if pkg.parent != root else "."
            for name in sorted(scripts):
                lname = name.lower()
                if name in ("test", "lint", "typecheck") or "coverage" in lname or lname in {"test:coverage", "coverage"}:
                    frameworks.add("node")
                    display = f"{prefix}npm {name}".strip()
                    argv = ["npm", "test"] if name == "test" else ["npm", "run", name]
                    if cwd != ".":
                        display = f"{cwd} {display}"
                    commands.append({"name": display, "argv": argv, "cwd": cwd, "scope": "all", "script": name})
        except Exception:
            pass
    pkg = root / "package.json"
    if pkg.exists():
        add_node_scripts(pkg)
    for pkg in sorted(root.glob("apps/*/package.json"))[:20]:
        add_node_scripts(pkg)
    for pkg in sorted(root.glob("packages/*/package.json"))[:20]:
        add_node_scripts(pkg)
    if (root / "go.mod").exists():
        frameworks.add("go"); commands.append({"name": "go test", "argv": ["go", "test", "./..."], "scope": "all"})
    if (root / "Cargo.toml").exists():
        frameworks.add("rust"); commands.append({"name": "cargo test", "argv": ["cargo", "test"], "scope": "all"})
    out = {"frameworks": sorted(frameworks), "commands": commands, "focused_commands": [c for c in commands if c.get("scope") == "focused"]}
    eval_telemetry.log_event("tests_discovered", workspace_path=str(root), frameworks=out["frameworks"], command_count=len(commands), focused_count=len(out["focused_commands"]))
    return out


def command_by_name(workspace_path: str, name: str) -> dict | None:
    for cmd in discover(workspace_path)["commands"]:
        if cmd["name"] == name:
            return cmd
    return None


def parse_failures(stdout: str, stderr: str) -> list[dict]:
    text = stdout + "\n" + stderr
    failures = []
    for m in re.finditer(r"FAILED\s+([^\s:]+)(?:::([^\s]+))?", text):
        failures.append({"file": m.group(1), "test": m.group(2), "message": "pytest failure"})
    for m in re.finditer(r"File \"([^\"]+)\", line (\d+)", text):
        failures.append({"file": m.group(1), "line": int(m.group(2)), "message": "traceback location"})
    return failures[:50]


def run_discovered(workspace_path: str, command_name: str, timeout_seconds: int = 120, validation_mode: str | None = None, target_ref: str | None = None) -> dict:
    cmd = command_by_name(workspace_path, command_name)
    if not cmd:
        return {"error": {"code": "command_not_discovered", "message": "Only discovered commands may be executed."}, "status": 400}
    from pathlib import Path
    root = ensure_under_allowed_root(workspace_path)
    cwd = root if cmd.get("cwd", ".") == "." else root / cmd.get("cwd")
    result = run_validation_command(name=command_name, argv=cmd["argv"], cwd=cwd, timeout_seconds=timeout_seconds, validation_mode=validation_mode, target_ref=target_ref)
    stdout = result.get("stdout_tail", "")
    stderr = result.get("stderr_tail", "")
    passed = result["status"] == "passed"
    eval_telemetry.log_event("tests_run", workspace_path=workspace_path, command_name=command_name, argv=cmd["argv"], passed=passed, exit_code=result["exitCode"], timeout=result.get("reason") == "timeout", validation_status=result["status"], scope=result["scope"])
    return {
        "command_name": command_name,
        "argv": cmd["argv"],
        "passed": passed,
        "exit_code": result["exitCode"],
        "stdout_tail": stdout,
        "stderr_tail": stderr,
        "failures": parse_failures(stdout, stderr),
        "timeout": result.get("reason") == "timeout",
        "repoPreflight": result.get("preflight") or git_preflight(workspace_path),
        "validationResult": result,
    }


def quality_commands(workspace_path: str) -> list[dict]:
    root = ensure_under_allowed_root(workspace_path)
    commands = []
    if (root / "pyproject.toml").exists() or (root / "requirements.txt").exists() or (root / "pytest.ini").exists():
        commands.append({"name": "compileall", "argv": ["python", "-m", "compileall", "."]})
    pkg = root / "package.json"
    if pkg.exists():
        try:
            scripts = json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {})
            for name in ("lint", "typecheck"):
                if name in scripts:
                    commands.append({"name": f"npm {name}", "argv": ["npm", "run", name]})
        except Exception:
            pass
    return commands
