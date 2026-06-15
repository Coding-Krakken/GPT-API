import json

from fastapi.testclient import TestClient

from main import app
from utils.audit import redact_and_cap, redact_text


def test_audit_redacts_and_caps_sensitive_output():
    raw = "API_KEY=abc123 SECRET=topsecret sk-abcdefghijklmnopqrstuvwxyz1234567890 " + ("x" * 9000)
    safe, meta = redact_and_cap(raw, max_bytes=256)
    assert "abc123" not in safe
    assert "topsecret" not in safe
    assert "sk-abcdefghijklmnopqrstuvwxyz1234567890" not in safe
    assert "<redacted" in safe or "=<redacted>" in safe
    assert meta["result_redacted"] is True
    assert meta["result_truncated"] is True
    assert meta["result_bytes"] > 256


def test_shell_audit_redacts_result(tmp_path, monkeypatch, auth_headers):
    audit_log = tmp_path / "audit.log"
    monkeypatch.setenv("AUDIT_LOG_PATH", str(audit_log))
    client = TestClient(app)
    resp = client.post(
        "/shell",
        headers=auth_headers,
        json={"command": "echo API_KEY=abc123 SECRET=topsecret sk-abcdefghijklmnopqrstuvwxyz1234567890"},
    )
    assert resp.status_code == 200
    entry = json.loads(audit_log.read_text().splitlines()[-1])
    assert "abc123" not in entry["result"]
    assert "topsecret" not in entry["result"]
    assert "sk-abcdefghijklmnopqrstuvwxyz1234567890" not in entry["result"]
    assert entry["result_redacted"] is True
    assert "result_bytes" in entry


def test_shell_command_too_long_has_recommended_alternatives(client, auth_headers):
    resp = client.post("/shell", headers=auth_headers, json={"command": "x" * 4097})
    assert resp.status_code == 200
    err = resp.json()["result"]["error"]
    assert err["code"] == "command_too_long"
    assert "/script/run" in " ".join(err["recommended_alternatives"])


def test_script_run_supports_large_script_and_redacts_output(client, auth_headers):
    content = "echo SECRET=topsecret\nprintf 'x%.0s' {1..5000}\necho\n"
    resp = client.post(
        "/script/run",
        headers=auth_headers,
        json={"language": "bash", "content": content, "max_output_bytes": 1024},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["exit_code"] == 0
    assert data["stdout_truncated"] is True
    assert "topsecret" not in data["stdout"]
    assert "<redacted>" in data["stdout"]
    assert data["script_path"] is None


def test_script_run_timeout_is_structured(client, auth_headers):
    resp = client.post(
        "/script/run",
        headers=auth_headers,
        json={"language": "bash", "content": "sleep 2", "timeout_seconds": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == 408
    assert data["error"]["code"] == "timeout"


def test_code_timeout_is_structured(client, auth_headers):
    resp = client.post(
        "/code",
        headers=auth_headers,
        json={"action": "run", "language": "python", "content": "import time\ntime.sleep(2)\n", "timeout_seconds": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["status"] == 408
    assert data["result"]["error"]["code"] == "timeout"


def test_code_run_redacts_stdout(client, auth_headers):
    resp = client.post(
        "/code",
        headers=auth_headers,
        json={"action": "run", "language": "python", "content": "print('API_KEY=abc123 SECRET=topsecret')"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["exit_code"] == 0
    assert "abc123" not in data["result"]["stdout"]
    assert "topsecret" not in data["result"]["stdout"]
    assert "<redacted>" in data["result"]["stdout"]


def test_redact_text_handles_common_secret_shapes():
    safe = redact_text("password=abc ghp_abcdefghijklmnopqrstuvwxyz123456 DATABASE_URL=postgres://u:p@h/db")
    assert "abc" not in safe
    assert "ghp_abcdefghijklmnopqrstuvwxyz123456" not in safe
    assert "postgres://u:p@h/db" not in safe
