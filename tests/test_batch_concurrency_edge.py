import os
import pytest
import threading
import time

def test_batch_shell_concurrent(client, auth_headers):
    # Test concurrent shell actions in a batch
    payload = {
        "operations": [
            {"action": "shell", "args": {"command": f"echo batch_{i}"}} for i in range(5)
        ]
    }
    response = client.post("/batch", headers=auth_headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    for i, result in enumerate(data["results"]):
        assert result["action"] == "shell"
        assert result["status"] == 200
        assert f"batch_{i}" in result["stdout"]

def test_batch_code_content_mix(client, auth_headers, temp_dir):
    # Test batch with both path and content for code actions
    fname = os.path.join(temp_dir, "batch_code_test.py")
    with open(fname, "w") as f:
        f.write("print('file path')\n")
    payload = {
        "operations": [
            {"action": "code", "args": {"action": "run", "path": fname, "language": "python"}},
            {"action": "code", "args": {"action": "run", "content": "print('in-memory')\n", "language": "python"}},
            {"action": "code", "args": {"action": "explain", "content": "print('should fail')\n", "language": "python"}},
        ]
    }
    response = client.post("/batch", headers=auth_headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    # First should succeed, second should succeed, third should fail with unsupported_content
    assert data["results"][0]["action"] == "code"
    assert data["results"][1]["action"] == "code"
    assert data["results"][2]["action"] == "code"
    assert data["results"][2]["result"]["error"]["code"] == "unsupported_content"

def test_batch_invalid_ops(client, auth_headers):
    # Test batch with invalid/malformed operations
    payload = {"operations": [None, 123, {"foo": "bar"}]}
    response = client.post("/batch", headers=auth_headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    for result in data["results"]:
        assert result["status"] == 400

def test_batch_concurrent_file_ops(client, auth_headers, temp_dir):
    # Test concurrent file write/delete in batch
    files = [os.path.join(temp_dir, f"batchfile_{i}.txt") for i in range(3)]
    payload = {"operations": [
        {"action": "files", "args": {"action": "write", "path": fname, "content": "data"}} for fname in files
    ] + [
        {"action": "files", "args": {"action": "delete", "path": fname}} for fname in files
    ]}
    response = client.post("/batch", headers=auth_headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    # All writes and deletes should succeed
    for result in data["results"]:
        response = client.post("/batch", headers=auth_headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    # All writes and deletes should succeed
    for result in data["results"]:
        assert result["action"] == "files"
        assert result["result"]["status"] == 200
