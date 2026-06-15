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
