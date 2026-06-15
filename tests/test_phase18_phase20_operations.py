from pathlib import Path


def _error_code(payload):
    error = payload.get("error") or payload.get("result", {}).get("error") or {}
    return error.get("code")


def test_shell_destructive_command_requires_confirmation(client, auth_headers):
    response = client.post("/shell", headers=auth_headers, json={"command": "rm -rf /tmp/phase18-never-run"})
    assert response.status_code == 200
    data = response.json()
    assert _error_code(data) == "confirmation_required"
    assert data["status"] == 403


def test_shell_destructive_dry_run_allowed_with_confirmation(client, auth_headers):
    response = client.post(
        "/shell",
        headers=auth_headers,
        json={"command": "rm -rf /tmp/phase18-never-run", "dry_run": True, "confirm": True},
    )
    assert response.status_code == 200
    assert response.json()["dry_run"] is True


def test_file_delete_requires_confirmation(client, auth_headers, temp_file):
    response = client.post("/files", headers=auth_headers, json={"action": "delete", "path": temp_file})
    assert response.status_code == 200
    data = response.json()["result"]
    assert data["error"]["code"] == "confirmation_required"
    assert Path(temp_file).exists()


def test_file_delete_with_confirmation_succeeds(client, auth_headers, temp_file):
    response = client.post("/files", headers=auth_headers, json={"action": "delete", "path": temp_file, "confirm": True})
    assert response.status_code == 200
    assert response.json()["result"]["status"] == 200
    assert not Path(temp_file).exists()


def test_package_install_requires_confirmation_before_dry_run(client, auth_headers):
    response = client.post(
        "/package",
        headers=auth_headers,
        json={"manager": "pip", "action": "install", "package": "example", "dry_run": True},
    )
    assert response.status_code == 200
    assert response.json()["error"]["code"] == "confirmation_required"


def test_git_push_requires_confirmation(client, auth_headers, temp_git_repo):
    response = client.post("/git", headers=auth_headers, json={"action": "push", "path": temp_git_repo, "dry_run": True})
    assert response.status_code == 200
    assert response.json()["error"]["code"] == "confirmation_required"


def test_supervision_and_rotation_assets_exist():
    root = Path(__file__).resolve().parents[1]
    for rel in [
        "config/policy.yaml",
        "utils/operation_policy.py",
        "scripts/start.sh",
        "scripts/stop.sh",
        "scripts/restart.sh",
        "scripts/status.sh",
        "deploy/systemd/gpt-api.service",
        "deploy/logrotate/gpt-api",
    ]:
        assert (root / rel).exists(), rel
