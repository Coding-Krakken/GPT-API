import os
import requests
import pytest
import threading
import time

API_KEY = os.getenv("API_KEY", "9e2b7c8a-4f1e-4b2a-9d3c-7f6e5a1b2c3d")
BASE_URL = "http://localhost:8000"
HEADERS = {"x-api-key": API_KEY, "Content-Type": "application/json"}

def test_batch_shell_concurrent():
    # Test concurrent shell actions in a batch
    payload = {
        "operations": [
            {"action": "shell", "args": {"command": f"echo batch_{i}"}} for i in range(5)
        ]
    }
    r = requests.post(BASE_URL + "/batch", headers=HEADERS, json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    for i, result in enumerate(data["results"]):
        assert result["action"] == "shell"
        assert result["status"] == 200
        assert f"batch_{i}" in result["stdout"]

def test_batch_code_content_mix():
    # Test batch with both path and content for code actions
    fname = "batch_code_test.py"
    with open(fname, "w") as f:
        f.write("print('file path')\n")
    payload = {
        "operations": [
            {"action": "code", "args": {"action": "run", "path": fname, "language": "python"}},
            {"action": "code", "args": {"action": "run", "content": "print('in-memory')\n", "language": "python"}},
            {"action": "code", "args": {"action": "explain", "content": "print('should fail')\n", "language": "python"}},
        ]
    }
    r = requests.post(BASE_URL + "/batch", headers=HEADERS, json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    # First should succeed, second should succeed, third should fail with unsupported_content
    assert data["results"][0]["action"] == "code"
    assert data["results"][1]["action"] == "code"
    assert data["results"][2]["action"] == "code"
    assert data["results"][2]["result"]["error"]["code"] == "unsupported_content"
    os.remove(fname)

def test_batch_invalid_ops():
    # Test batch with invalid/malformed operations
    payload = {"operations": [None, 123, {"foo": "bar"}]}
    r = requests.post(BASE_URL + "/batch", headers=HEADERS, json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    for result in data["results"]:
        assert result["status"] == 400

def test_batch_concurrent_file_ops():
    # Test concurrent file write/delete in batch
    files = [f"batchfile_{i}.txt" for i in range(3)]
    payload = {"operations": [
        {"action": "files", "args": {"action": "write", "path": fname, "content": "data"}} for fname in files
    ] + [
        {"action": "files", "args": {"action": "delete", "path": fname}} for fname in files
    ]}
    r = requests.post(BASE_URL + "/batch", headers=HEADERS, json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    # All writes and deletes should succeed
    for result in data["results"]:
        assert result["action"] == "files"
        assert result["result"]["status"] == 200
