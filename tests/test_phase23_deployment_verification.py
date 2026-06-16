from pathlib import Path

from scripts import verify_deployment


ROOT = Path(__file__).resolve().parents[1]


def test_deployment_verifier_script_exists_and_documents_live_contract():
    script = ROOT / "scripts" / "verify_deployment.py"
    assert script.exists()
    text = script.read_text(encoding="utf-8")
    for phrase in [
        "--live",
        "--public",
        "--require-live",
        "--expect-commit",
        "coding-gpt-core-openapi.yaml",
        "/agent/coding-task",
        "/repo/instructions",
        "/env/discover",
        "deployment_verification_",
        "ngrok-skip-browser-warning",
    ]:
        assert phrase in text


def test_static_schema_deployment_checks_cover_required_action_paths():
    core_required = verify_deployment.REQUIRED_CORE_ACTION_PATHS
    full_required = verify_deployment.REQUIRED_FULL_CODING_ACTION_PATHS
    assert "/agent/coding-task" in core_required
    assert "/repo/preflight" in core_required
    assert "/env/prepare-dry-run" in core_required
    assert "/coding/env/action" not in core_required
    assert "/coding/env/action" in full_required
    for filename, required in [
        ("coding-openapi.yaml", full_required),
        ("coding-gpt-core-openapi.yaml", core_required),
    ]:
        ok, summary, detail = verify_deployment.validate_schema_file(ROOT / filename, required_paths=required)
        assert ok, (summary, detail)
        assert detail["missing_paths"] == []
        assert detail["bad_servers"] == []
        assert detail["long_descriptions"] == []
        assert detail["bare_object_schemas"] == []


def test_deployment_verifier_writes_json_and_markdown_reports(tmp_path):
    output_dir = tmp_path / "deploy-reports"
    rc = verify_deployment.main_args_for_tests([
        "--allow-dirty",
        "--output-dir",
        str(output_dir),
    ]) if hasattr(verify_deployment, "main_args_for_tests") else None
    if rc is None:
        # Backward-compatible path if the helper is not present during partial edits.
        import subprocess, sys
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_deployment.py"), "--allow-dirty", "--output-dir", str(output_dir)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=120,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
    else:
        assert rc == 0
    json_reports = list(output_dir.glob("deployment_verification_*.json"))
    md_reports = list(output_dir.glob("deployment_verification_*.md"))
    assert json_reports
    assert md_reports
    text = json_reports[0].read_text(encoding="utf-8")
    assert '"status": "passed"' in text
    assert "in_process_/health_healthy" in text
    assert "schema_coding-gpt-core-openapi.yaml" in text


def test_phase21_runbook_mentions_deployment_verifier():
    text = (ROOT / "docs" / "PHASE21_22_DOCUMENTATION_AND_VERIFICATION.md").read_text(encoding="utf-8")
    assert "scripts/verify_deployment.py" in text
    assert "--live" in text
    assert "--public" in text
    assert "deployment verification report" in text.lower()
