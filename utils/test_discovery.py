from __future__ import annotations

import json
import re
from pathlib import Path

from utils.policy import ensure_under_allowed_root
from utils.safe_subprocess import run_checked
from utils import eval_telemetry


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
    pkg = root / "package.json"
    if pkg.exists():
        try:
            scripts = json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {})
            for name in ("test", "lint", "typecheck"):
                if name in scripts:
                    frameworks.add("node")
                    commands.append({"name": f"npm {name}", "argv": ["npm", "run", name] if name != "test" else ["npm", "test"], "scope": "all"})
        except Exception:
            pass
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


def run_discovered(workspace_path: str, command_name: str, timeout_seconds: int = 120) -> dict:
    cmd = command_by_name(workspace_path, command_name)
    if not cmd:
        return {"error": {"code": "command_not_discovered", "message": "Only discovered commands may be executed."}, "status": 400}
    result = run_checked(cmd["argv"], workspace_path, timeout=timeout_seconds)
    eval_telemetry.log_event("tests_run", workspace_path=workspace_path, command_name=command_name, argv=cmd["argv"], passed=result["passed"], exit_code=result["exit_code"], timeout=result.get("timeout", False))
    return {
        "command_name": command_name,
        "argv": cmd["argv"],
        "passed": result["passed"],
        "exit_code": result["exit_code"],
        "stdout_tail": result["stdout"][-8000:],
        "stderr_tail": result["stderr"][-8000:],
        "failures": parse_failures(result["stdout"], result["stderr"]),
        "timeout": result.get("timeout", False),
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
