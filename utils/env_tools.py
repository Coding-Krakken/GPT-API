from __future__ import annotations

from utils.policy import ensure_under_allowed_root, PolicyError
from utils.safe_subprocess import run_checked


def discover(workspace_path: str) -> dict:
    root = ensure_under_allowed_root(workspace_path)
    managers = []
    manifests = []
    def has(name: str) -> bool:
        p = root / name
        if p.exists():
            manifests.append(name)
            return True
        return False
    py = "uv" if has("uv.lock") else "poetry" if has("poetry.lock") else "pdm" if has("pdm.lock") else "pip" if (has("requirements.txt") or has("pyproject.toml")) else None
    if py: managers.append({"language": "python", "manager": py})
    node = "pnpm" if has("pnpm-lock.yaml") else "yarn" if has("yarn.lock") else "bun" if (has("bun.lockb") or has("bun.lock")) else "npm" if (has("package-lock.json") or has("package.json")) else None
    if node: managers.append({"language": "node", "manager": node})
    if has("go.mod"): managers.append({"language": "go", "manager": "go"})
    if has("Cargo.toml"): managers.append({"language": "rust", "manager": "cargo"})
    if has("pom.xml"): managers.append({"language": "java", "manager": "maven"})
    if has("build.gradle") or has("build.gradle.kts"): managers.append({"language": "java", "manager": "gradle"})
    devcontainer = (root / ".devcontainer" / "devcontainer.json").exists()
    compose = any((root / n).exists() for n in ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"])
    return {"workspace_path": str(root), "managers": managers, "manifests": sorted(set(manifests)), "devcontainer": devcontainer, "docker_compose": compose}


def doctor(workspace_path: str) -> dict:
    root = ensure_under_allowed_root(workspace_path)
    checks = []
    commands = [["python", "--version"], ["uv", "--version"], ["poetry", "--version"], ["pdm", "--version"], ["node", "--version"], ["npm", "--version"], ["pnpm", "--version"], ["yarn", "--version"], ["bun", "--version"], ["go", "version"], ["cargo", "--version"], ["mvn", "--version"], ["gradle", "--version"], ["docker", "--version"], ["gh", "--version"], ["git", "--version"]]
    for argv in commands:
        result = run_checked(argv, root, timeout=10)
        checks.append({"tool": argv[0], "available": result["exit_code"] == 0, "stdout": result["stdout"].strip()[:200], "stderr": result["stderr"].strip()[:200]})
    return {"workspace_path": str(root), "checks": checks, "available_tools": [c["tool"] for c in checks if c["available"]]}


def prepare_plan(workspace_path: str) -> dict:
    root = ensure_under_allowed_root(workspace_path)
    steps = []
    d = discover(str(root))
    for m in d["managers"]:
        manager = m["manager"]
        if manager == "uv": steps.append({"manager": "uv", "argv": ["uv", "sync"], "requires_approval": True, "network": True})
        elif manager == "poetry": steps.append({"manager": "poetry", "argv": ["poetry", "install"], "requires_approval": True, "network": True})
        elif manager == "pdm": steps.append({"manager": "pdm", "argv": ["pdm", "install"], "requires_approval": True, "network": True})
        elif manager == "pip":
            if (root / "requirements.txt").exists(): steps.append({"manager": "pip", "argv": ["python", "-m", "pip", "install", "-r", "requirements.txt"], "requires_approval": True, "network": True})
            elif (root / "pyproject.toml").exists(): steps.append({"manager": "pip", "argv": ["python", "-m", "pip", "install", "-e", ".[dev]"], "requires_approval": True, "network": True})
        elif manager == "pnpm": steps.append({"manager": "pnpm", "argv": ["pnpm", "install", "--frozen-lockfile"], "requires_approval": True, "network": True})
        elif manager == "yarn": steps.append({"manager": "yarn", "argv": ["yarn", "install", "--frozen-lockfile"], "requires_approval": True, "network": True})
        elif manager == "bun": steps.append({"manager": "bun", "argv": ["bun", "install", "--frozen-lockfile"], "requires_approval": True, "network": True})
        elif manager == "npm": steps.append({"manager": "npm", "argv": ["npm", "ci"] if (root / "package-lock.json").exists() else ["npm", "install"], "requires_approval": True, "network": True})
        elif manager == "go": steps.append({"manager": "go", "argv": ["go", "mod", "download"], "requires_approval": True, "network": True})
        elif manager == "cargo": steps.append({"manager": "cargo", "argv": ["cargo", "fetch"], "requires_approval": True, "network": True})
        elif manager == "maven": steps.append({"manager": "maven", "argv": ["mvn", "test", "-DskipTests"], "requires_approval": True, "network": True})
        elif manager == "gradle": steps.append({"manager": "gradle", "argv": ["gradle", "dependencies"], "requires_approval": True, "network": True})
    if d.get("devcontainer"): steps.append({"manager": "devcontainer", "argv": ["devcontainer", "up", "--workspace-folder", str(root)], "requires_approval": True, "network": True})
    return {"workspace_path": str(root), "dry_run": True, "steps": steps, "discovery": d}


def prepare_approved(workspace_path: str, approved: bool = False) -> dict:
    if not approved:
        raise PolicyError("approval_required", "Environment preparation requires explicit approval.")
    root = ensure_under_allowed_root(workspace_path)
    results = []
    for step in prepare_plan(str(root))["steps"]:
        result = run_checked(step["argv"], root, timeout=900)
        results.append({"argv": step["argv"], "manager": step.get("manager"), "passed": result["passed"], "exit_code": result["exit_code"], "stdout_tail": result["stdout"][-4000:], "stderr_tail": result["stderr"][-4000:]})
        if not result["passed"]:
            break
    return {"workspace_path": str(root), "results": results, "passed": all(r["passed"] for r in results)}
