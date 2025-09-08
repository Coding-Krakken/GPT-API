import os
import pytest

def test_batch_code_error_propagation(client, auth_headers, temp_dir):
    # Test batch with a valid and an invalid code action
    fname = os.path.join(temp_dir, "batch_code_valid.py")
    with open(fname, "w") as f:
        f.write("print('ok')\n")
    payload = {
        "operations": [
            {"action": "code", "args": {"action": "run", "path": fname, "language": "python"}},
            {"action": "code", "args": {"action": "run", "path": "../etc/passwd", "language": "python"}},
            {"action": "code", "args": {"action": "run", "content": "print('bad',)", "language": "python", "args": "; rm -rf /"}},
        ]
    }
    response = client.post("/batch", headers=auth_headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    # First should succeed, second should fail with invalid_path, third should fail with invalid_args
    assert data["results"][0]["action"] == "code"
    assert "stdout" in data["results"][0]["result"]
    assert data["results"][1]["action"] == "code"
    assert data["results"][1]["result"]["error"]["code"] == "invalid_path"
    assert data["results"][2]["action"] == "code"
    assert data["results"][2]["result"]["error"]["code"] == "invalid_args"

def test_batch_code_structured_error(client, auth_headers):
    # Test batch with a code action that triggers a subprocess error
    payload = {
        "operations": [
            {"action": "code", "args": {"action": "run", "content": "raise Exception('fail')", "language": "python"}},
        ]
    }
    response = client.post("/batch", headers=auth_headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert data["results"][0]["action"] == "code"
    # Should return error with code 'execution_error' or 'subprocess_error'
    assert "result" in data["results"][0]
    assert "error" in data["results"][0]["result"]
    assert data["results"][0]["result"]["error"]["code"] in ("execution_error", "subprocess_error")
