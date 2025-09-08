import os
import requests
import pytest

API_KEY = os.getenv("API_KEY", "9e2b7c8a-4f1e-4b2a-9d3c-7f6e5a1b2c3d")
BASE_URL = "https://gpt-api.ngrok.app"
HEADERS = {"x-api-key": API_KEY, "Content-Type": "application/json"}

@pytest.mark.parametrize("endpoint, method, payload, expect_status", [
    ("/system/", "GET", None, 200),
    ("/files", "POST", {"action": "write", "path": "testfile.txt", "content": "Hello, test!"}, 200),
    ("/files", "POST", {"action": "read", "path": "testfile.txt"}, 200),
    ("/files", "POST", {"action": "stat", "path": "testfile.txt"}, 200),
    ("/files", "POST", {"action": "exists", "path": "testfile.txt"}, 200),
    ("/files", "POST", {"action": "delete", "path": "testfile.txt"}, 200),
    ("/shell", "POST", {"command": "echo 'pytest-shell'"}, 200),
    ("/code", "POST", {"action": "run", "path": "main.py", "language": "python"}, 200),
    ("/monitor", "POST", {"type": "cpu"}, 200),
    ("/git", "POST", {"action": "status", "path": "."}, 200),
    ("/package", "POST", {"manager": "pip", "action": "list"}, 200),
    # Expanded /apps test: list and try to open a common app (may fail if not installed, but should not 500)
    ("/apps", "POST", {"action": "list", "app": None}, 200),
    ("/apps", "POST", {"action": "open", "app": "firefox"}, 200),
    # Expanded /refactor test: dry run and real run (real run may fail if file is protected, but should not 500)
    ("/refactor", "POST", {"search": "API_KEY", "replace": "API_TOKEN", "files": ["cli.py"], "dry_run": True}, 200),
    ("/refactor", "POST", {"search": "API_KEY", "replace": "API_TOKEN", "files": ["cli.py"], "dry_run": False}, 200),
    # Expanded /batch test: multiple shell commands
    ("/batch", "POST", {"operations": [
        {"action": "shell", "args": {"command": "echo 'batch1'"}},
        {"action": "shell", "args": {"command": "echo 'batch2'"}}
    ]}, 200),
])
def test_endpoint(endpoint, method, payload, expect_status):
    url = BASE_URL + endpoint
    if method == "GET":
        r = requests.get(url, headers=HEADERS)
    else:
        r = requests.post(url, headers=HEADERS, json=payload)
    assert r.status_code == expect_status, f"{endpoint} {method} failed: {r.text}"


@pytest.mark.parametrize("endpoint, method, payload, expect_status, use_auth", [
    ("/files", "POST", {"action": "read", "path": "/nonexistent/file.txt"}, 200, True),
    ("/system/", "GET", None, 403, False),
])
def test_error_cases(endpoint, method, payload, expect_status, use_auth):
    url = BASE_URL + endpoint
    headers = dict(HEADERS) if use_auth else {"Content-Type": "application/json"}
    if method == "GET":
        r = requests.get(url, headers=headers)
    else:
        r = requests.post(url, headers=headers, json=payload)
    assert r.status_code == expect_status, f"Expected {expect_status}, got {r.status_code}: {r.text}"

def test_bulk_file_ops():
    # Write multiple files, list, delete all
    files = [f"bulkfile_{i}.txt" for i in range(3)]
    for fname in files:
        r = requests.post(BASE_URL + "/files", headers=HEADERS, json={"action": "write", "path": fname, "content": "bulk"})
        assert r.status_code == 200
    r = requests.post(BASE_URL + "/files", headers=HEADERS, json={"action": "list", "path": "."})
    assert r.status_code == 200
    listed = r.json()
    for fname in files:
        assert any(fname in str(item) for item in listed.values()), f"{fname} not listed"
    for fname in files:
        r = requests.post(BASE_URL + "/files", headers=HEADERS, json={"action": "delete", "path": fname})
        assert r.status_code == 200

def test_shell_side_effect():
    # Create a file using shell, then check existence
    fname = "shell_created.txt"
    cmd = f"echo 'created' > {fname}"
    r = requests.post(BASE_URL + "/shell", headers=HEADERS, json={"command": cmd})
    assert r.status_code == 200
    r = requests.post(BASE_URL + "/files", headers=HEADERS, json={"action": "exists", "path": fname})
    assert r.status_code == 200
    assert r.json()["result"].get("exists"), "File not created by shell"
    # Cleanup
    requests.post(BASE_URL + "/files", headers=HEADERS, json={"action": "delete", "path": fname})

def test_auth_variants():
    # Valid key
    r = requests.get(BASE_URL + "/system/", headers=HEADERS)
    assert r.status_code == 200
    # Invalid key
    bad_headers = dict(HEADERS)
    bad_headers["x-api-key"] = "bad-key"
    r = requests.get(BASE_URL + "/system/", headers=bad_headers)
    assert r.status_code == 403
    # Missing key
    r = requests.get(BASE_URL + "/system/", headers={"Content-Type": "application/json"})
    assert r.status_code == 403
