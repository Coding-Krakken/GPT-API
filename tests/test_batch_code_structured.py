import os
import requests
import pytest

API_KEY = os.getenv("API_KEY", "9e2b7c8a-4f1e-4b2a-9d3c-7f6e5a1b2c3d")
BASE_URL = "http://localhost:8000"
HEADERS = {"x-api-key": API_KEY, "Content-Type": "application/json"}

def test_batch_code_error_propagation():
    # Test batch with a valid and an invalid code action
    fname = "batch_code_valid.py"
    with open(fname, "w") as f:
        f.write("print('ok')\n")
    payload = {
        "operations": [
            {"action": "code", "args": {"action": "run", "path": fname, "language": "python"}},
            {"action": "code", "args": {"action": "run", "path": "../etc/passwd", "language": "python"}},
            {"action": "code", "args": {"action": "run", "content": "print('bad',)", "language": "python", "args": "; rm -rf /"}},
        ]
    }
    r = requests.post(BASE_URL + "/batch", headers=HEADERS, json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    # First should succeed, second should fail with invalid_path, third should fail with invalid_args
    assert data["results"][0]["action"] == "code"
    assert "stdout" in data["results"][0]["result"]
    assert data["results"][1]["action"] == "code"
    assert data["results"][1]["error"]["code"] == "invalid_path"
    assert data["results"][2]["action"] == "code"
    assert data["results"][2]["error"]["code"] == "invalid_args"
    os.remove(fname)

def test_batch_code_structured_error():
    # Test batch with a code action that triggers a subprocess error
    payload = {
        "operations": [
            {"action": "code", "args": {"action": "run", "content": "raise Exception('fail')", "language": "python"}},
        ]
    }
    r = requests.post(BASE_URL + "/batch", headers=HEADERS, json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert data["results"][0]["action"] == "code"
    # Should return error with code 'execution_error' or 'subprocess_error'
    assert "error" in data["results"][0]
    assert data["results"][0]["error"]["code"] in ("execution_error", "subprocess_error")
