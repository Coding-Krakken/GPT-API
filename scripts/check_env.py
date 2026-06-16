#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "requirements.txt"
CORE_IMPORTS = {
    "fastapi": "fastapi",
    "pydantic": "pydantic",
    "pytest": "pytest",
    "httpx": "httpx",
    "PyYAML": "yaml",
    "uvicorn": "uvicorn",
}
ESSENTIAL_COMMANDS = ["git", "bash"]
OPTIONAL_COMMANDS = ["curl"]


@dataclass
class Check:
    name: str
    status: str
    severity: str
    summary: str
    detail: Any = None


def add(checks: list[Check], name: str, ok: bool, summary: str, *, severity: str = "high", detail: Any = None) -> None:
    checks.append(Check(name=name, status="passed" if ok else "failed", severity=severity, summary=summary, detail=detail))


def parse_requirements() -> dict[str, str]:
    packages: dict[str, str] = {}
    if not REQUIREMENTS.exists():
        return packages
    for raw in REQUIREMENTS.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        if ";" in line:
            line = line.split(";", 1)[0].strip()
        for sep in ["==", ">=", "<=", "~=", ">", "<"]:
            if sep in line:
                name = line.split(sep, 1)[0].strip()
                break
        else:
            name = line.strip()
        if name:
            packages[name] = raw.strip()
    return packages


def import_name_for_package(package: str) -> str:
    normalized = package.lower().replace("-", "_")
    overrides = {
        "python_dotenv": "dotenv",
        "pyyaml": "yaml",
        "pynacl": "nacl",
        "typing_extensions": "typing_extensions",
        "typing_inspection": "typing_inspection",
        "pydantic_core": "pydantic_core",
    }
    return overrides.get(normalized, normalized)


def check_import(module: str) -> tuple[bool, str]:
    try:
        imported = importlib.import_module(module)
        version = getattr(imported, "__version__", "unknown")
        return True, str(version)
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def run_git(args: list[str]) -> tuple[bool, str]:
    try:
        proc = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, timeout=15)
        output = (proc.stdout or proc.stderr).strip()
        return proc.returncode == 0, output
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def build_report(*, strict: bool, check_all_requirements: bool, include_optional_commands: bool) -> dict[str, Any]:
    checks: list[Check] = []
    add(checks, "python_version", sys.version_info >= (3, 11), sys.version.split()[0], severity="critical", detail=sys.version)
    add(checks, "python_executable", bool(sys.executable), sys.executable, severity="medium")
    add(checks, "repo_root", ROOT.exists(), str(ROOT), severity="critical")
    add(checks, "requirements_file", REQUIREMENTS.exists(), str(REQUIREMENTS), severity="critical")

    for command in ESSENTIAL_COMMANDS:
        path = shutil.which(command)
        add(checks, f"command_{command}", bool(path), path or "not found", severity="critical")
    if include_optional_commands:
        for command in OPTIONAL_COMMANDS:
            path = shutil.which(command)
            add(checks, f"command_{command}", bool(path), path or "not found", severity="medium")

    ok, detail = run_git(["rev-parse", "--show-toplevel"])
    add(checks, "git_repo_detected", ok and Path(detail).resolve() == ROOT.resolve(), detail, severity="high")
    ok, detail = run_git(["status", "--short"])
    add(checks, "git_worktree_clean", ok and not detail, "clean" if ok and not detail else detail, severity="medium")

    packages = parse_requirements()
    add(checks, "requirements_parse", bool(packages), f"packages={len(packages)}", severity="high")

    for _package, module in CORE_IMPORTS.items():
        ok, detail = check_import(module)
        add(checks, f"core_import_{module}", ok, detail, severity="critical")

    missing_declared: list[dict[str, str]] = []
    if check_all_requirements:
        for package, requirement in sorted(packages.items(), key=lambda item: item[0].lower()):
            module = import_name_for_package(package)
            ok, detail = check_import(module)
            if not ok:
                missing_declared.append({"package": package, "module": module, "requirement": requirement, "error": detail})
        add(
            checks,
            "declared_requirements_importable",
            not missing_declared,
            "all declared packages importable" if not missing_declared else f"missing_or_unimportable={len(missing_declared)}",
            severity="critical" if strict else "medium",
            detail=missing_declared,
        )

    failed = [asdict(check) for check in checks if check.status != "passed"]
    strict_failures = [item for item in failed if item["severity"] in {"critical", "high"}]
    status = "passed" if not (strict and strict_failures) else "failed"
    return {
        "status": status,
        "strict": strict,
        "check_all_requirements": check_all_requirements,
        "python": sys.executable,
        "repo_root": str(ROOT),
        "checks": [asdict(check) for check in checks],
        "failed": failed,
        "summary": {
            "total": len(checks),
            "passed": len(checks) - len(failed),
            "failed": len(failed),
            "strict_blockers": len(strict_failures),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify GPT-API Python environment and bootstrap readiness.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when critical/high checks fail.")
    parser.add_argument("--check-all-requirements", action="store_true", help="Attempt to import every package declared in requirements.txt.")
    parser.add_argument("--include-optional-commands", action="store_true", help="Check optional command-line tools such as curl.")
    parser.add_argument("--json-output", help="Write the full JSON report to this path.")
    args = parser.parse_args()

    report = build_report(
        strict=args.strict,
        check_all_requirements=args.check_all_requirements,
        include_optional_commands=args.include_optional_commands,
    )
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.json_output:
        Path(args.json_output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
