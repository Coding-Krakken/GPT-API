from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_release_gate_script_exists_and_runs_core_checks():
    script = ROOT / "scripts" / "release_gate.sh"
    assert script.exists()
    text = script.read_text(encoding="utf-8")
    assert "scripts/ticket_index.py" in text
    assert "scripts/validate_openapi.py" in text
    assert "pytest -q" in text
    assert "git diff --exit-code" in text


def test_openapi_validator_script_exists():
    script = ROOT / "scripts" / "validate_openapi.py"
    assert script.exists()
    text = script.read_text(encoding="utf-8")
    assert "validate_server_urls" in text
    assert "validate_operation_ids" in text
    assert "ApiKeyAuth" in text


def test_healthcheck_script_is_nonempty_and_ci_safe():
    script = ROOT / "healthcheck.sh"
    assert script.exists()
    text = script.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in text
    assert "/health" in text
    assert "/healthz" in text
    assert "/api/health" in text
    assert "curl" in text


def test_release_gate_syntax_checks_healthcheck():
    script = ROOT / "scripts" / "release_gate.sh"
    text = script.read_text(encoding="utf-8")
    assert "bash -n healthcheck.sh" in text


def test_environment_bootstrap_scripts_exist_and_are_release_gated():
    bootstrap = ROOT / "scripts" / "bootstrap.sh"
    check_env = ROOT / "scripts" / "check_env.py"
    release_gate = ROOT / "scripts" / "release_gate.sh"
    assert bootstrap.exists()
    assert bootstrap.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash")
    assert "python -m pip install -r requirements.txt" in bootstrap.read_text(encoding="utf-8")
    assert check_env.exists()
    check_env_text = check_env.read_text(encoding="utf-8")
    assert "CORE_IMPORTS" in check_env_text
    assert "declared_requirements_importable" in check_env_text
    assert "--strict" in check_env_text
    assert "scripts/check_env.py --strict" in release_gate.read_text(encoding="utf-8")


def test_environment_checker_core_contract_runs():
    import json
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_env.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert proc.returncode == 0
    report = json.loads(proc.stdout)
    assert report["summary"]["total"] >= 8
    assert any(check["name"] == "requirements_file" for check in report["checks"])
    assert any(check["name"] == "core_import_fastapi" for check in report["checks"])
