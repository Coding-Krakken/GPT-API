import json
import subprocess
from pathlib import Path

from utils.validation_workflow import git_preflight, run_validation_command


def _init_git_repo(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)


def test_repo_preflight_reports_dirty_state(client, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setenv("REPO_ALLOWED_ROOTS", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    (repo / "changed.ts").write_text("const parsed: Record<string, any> = JSON.parse('{}') as any\n", encoding="utf-8")

    body = client.post("/repo/preflight", headers=auth_headers, json={"repo_path": str(repo)}).json()

    assert body["status"] == 200
    assert body["repoPreflight"]["isDirty"] is True
    assert "changed.ts" in body["repoPreflight"]["untrackedFiles"]
    assert body["repoPreflight"]["scopeIsolationWarning"]
    warnings = body["typeSafety"]["typeSafetyWarnings"]
    assert any(w["pattern"] in {"Record<string, any>", "as any"} for w in warnings)


def test_repo_preflight_discovers_security_and_ci_safe_checks(client, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setenv("REPO_ALLOWED_ROOTS", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    (repo / "package.json").write_text(json.dumps({"scripts": {"lint": "next lint", "test": "vitest run", "build": "next build"}}), encoding="utf-8")
    (repo / "export-route.ts").write_text("import fs from 'fs';\nconst data = JSON.parse('{}');\nfetch('https://example.com');\n// CSV export\n", encoding="utf-8")

    body = client.post("/repo/preflight", headers=auth_headers, json={"repo_path": str(repo)}).json()

    assert body["suggestedChecks"]["missingCiSafeLint"] is True
    assert any("npm run lint" in c for c in body["suggestedChecks"]["possiblyInteractiveChecks"])
    assert body["securityReview"]["securityReviewRequired"] is True
    checklist = body["securityReview"]["checklist"]
    assert "CSV/formula injection" in checklist
    assert "SSRF/proxy validation" in checklist


def test_validation_command_blocks_interactive_prompt(tmp_path, monkeypatch):
    monkeypatch.setenv("REPO_ALLOWED_ROOTS", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)

    result = run_validation_command(
        name="lint",
        argv=["python", "-c", "print('How would you like to configure ESLint?')"],
        cwd=repo,
        timeout_seconds=20,
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "Next.js lint attempted interactive ESLint setup."
    assert "eslint . --max-warnings=0" in result["recommendation"]
    assert result["scope"] == "clean-head"


def test_clean_validation_mode_uses_temp_worktree(client, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setenv("REPO_ALLOWED_ROOTS", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    (repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "tests"], cwd=repo, check=True, capture_output=True)
    (repo / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")

    body = client.post(
        "/test/run",
        headers=auth_headers,
        json={"workspace_path": str(repo), "command_name": "pytest", "timeout_seconds": 60, "validationMode": "clean-worktree"},
    ).json()

    assert body["passed"] is True
    assert body["repoPreflight"]["isDirty"] is True
    assert body["validationResult"]["scope"] == "temp-worktree"
    assert body["validationResult"]["status"] == "passed"
