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
