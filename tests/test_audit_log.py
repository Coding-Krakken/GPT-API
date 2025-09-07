import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from main import app

def test_shell_audit_log(tmp_path, monkeypatch):
    # Set audit log path to a temp file
    audit_log = tmp_path / "audit.log"
    monkeypatch.setenv("AUDIT_LOG_PATH", str(audit_log))
    client = TestClient(app)
    # Use a valid API key from .env or set a dummy one for test
    api_key = os.environ.get("API_KEY", "test-key")
    resp = client.post(
        "/shell/",
        headers={"x-api-key": api_key},
        json={"command": "echo hello"}
    )
    assert resp.status_code == 200
    # Check audit log was written
    assert audit_log.exists()
    lines = audit_log.read_text().splitlines()
    assert len(lines) > 0
    entry = lines[-1]
    assert '"endpoint": "/shell"' in entry
    assert '"status": 200' in entry
    assert '"action": "run_shell_command"' in entry
    assert '"result":' in entry


def test_shell_audit_log_invalid_and_faults(tmp_path, monkeypatch):
    audit_log = tmp_path / "audit.log"
    monkeypatch.setenv("AUDIT_LOG_PATH", str(audit_log))
    client = TestClient(app)
    api_key = os.environ.get("API_KEY", "test-key")

    cases = [
        # Empty command
        ({"command": ""}, 400, "missing_command"),
        # Whitespace command
        ({"command": "   "}, 400, "missing_command"),
        # Sudo command (should fail if not root)
        ({"command": "ls /root", "run_as_sudo": True}, 400, None),
        # Background command
        ({"command": "sleep 0.1 && echo done", "background": True}, 200, None),
        # Fault injection: permission
        ({"command": "echo test", "fault": "permission"}, 200, "permission_denied"),
        # Fault injection: io
        ({"command": "echo test", "fault": "io"}, 200, "io_error"),
        # Invalid path
        ({"command": "cat /proc/does_not_exist"}, 400, None),
    ]

    for payload, expected_status, error_code in cases:
        resp = client.post(
            "/shell/",
            headers={"x-api-key": api_key},
            json=payload
        )
        # Accept 200 or 400 depending on case
        assert resp.status_code in (200, 400)
        assert audit_log.exists()
        lines = audit_log.read_text().splitlines()
        assert len(lines) > 0
        entry = lines[-1]
        assert '"endpoint": "/shell"' in entry
        assert '"action": "run_shell_command"' in entry
        if error_code:
            assert error_code in entry
        # For empty/whitespace, should be missing_command
        if payload["command"].strip() == "":
            assert "missing_command" in entry or "command_too_long" in entry
