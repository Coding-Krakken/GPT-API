from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_phase21_phase22_runbook_documents_required_contracts():
    doc = ROOT / "docs" / "PHASE21_22_DOCUMENTATION_AND_VERIFICATION.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    lower_text = text.lower()
    for phrase in [
        "canonical service urls",
        "x-api-key",
        "slash policy",
        "health endpoints",
        "safe endpoint usage",
        "long-job workflow",
        "maintainer ticket workflow",
        "release_gate.sh",
        "smoke_local.py",
        "verify_deployment.py",
        "deployment verification report",
    ]:
        assert phrase in lower_text


def test_phase22_smoke_script_exists_and_covers_matrix():
    script = ROOT / "scripts" / "smoke_local.py"
    assert script.exists()
    text = script.read_text(encoding="utf-8")
    for phrase in [
        "/health",
        "/healthz",
        "/api/health",
        "/openapi.yaml",
        "/metrics",
        "/shell",
        "/files",
        "duplicate-slash",
        "/repo/overview",
        "/coding/repo/action",
    ]:
        assert phrase in text


def test_release_gate_runs_phase22_smoke_matrix():
    text = (ROOT / "scripts" / "release_gate.sh").read_text(encoding="utf-8")
    assert "scripts/smoke_local.py" in text


def test_readme_links_phase21_phase22_runbook():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "PHASE21_22_DOCUMENTATION_AND_VERIFICATION.md" in text
    assert "python3 scripts/smoke_local.py" in text


def test_phase22_deployment_verifier_is_release_gate_covered():
    release_gate = (ROOT / "scripts" / "release_gate.sh").read_text(encoding="utf-8")
    verifier = (ROOT / "scripts" / "verify_deployment.py").read_text(encoding="utf-8")
    assert "scripts/verify_deployment.py" in release_gate
    assert "--allow-dirty" in release_gate
    assert "--live" in verifier
    assert "--public" in verifier
    assert "--expect-commit" in verifier
