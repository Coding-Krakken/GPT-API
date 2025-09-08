import os
import pytest
import threading
import time

def test_code_run_invalid_language(client, auth_headers):
    payload = {"action": "run", "path": "test_code_endpoint.py", "language": "invalid_lang"}
    response = client.post("/code", headers=auth_headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["result"]["error"]["code"] == "unsupported_language"

def test_code_run_concurrent(client, auth_headers, temp_dir):
    # Create a temp file for concurrency test
    fname = os.path.join(temp_dir, "concurrent_test.py")
    with open(fname, "w") as f:
        f.write("print('concurrent')\n")
    payload = {"action": "run", "path": fname, "language": "python"}
    results = []
    def run_code():
        response = client.post("/code", headers=auth_headers, json=payload)
        results.append(response.status_code)
        if response.status_code == 200:
            data = response.json()
            if "result" in data and "error" in data["result"]:
                results.append(data["result"]["error"]["code"])
    threads = [threading.Thread(target=run_code) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # At least one should succeed, others may get concurrent_access error
    assert 200 in results
    assert any("concurrent_access" in str(results) for item in results)

def test_code_path_injection(client, auth_headers):
    payload = {"action": "run", "path": "../etc/passwd", "language": "python"}
    response = client.post("/code", headers=auth_headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["result"]["error"]["code"] == "invalid_path"

def test_code_path_too_long(client, auth_headers):
    long_path = "a" * 300 + ".py"
    payload = {"action": "run", "path": long_path, "language": "python"}
    response = client.post("/code", headers=auth_headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["result"]["error"]["code"] == "path_too_long"

def test_code_no_tests_found(client, auth_headers, temp_dir):
    fname = os.path.join(temp_dir, "no_tests.py")
    with open(fname, "w") as f:
        f.write("print('no tests')\n")
    payload = {"action": "test", "path": fname, "language": "python"}
    response = client.post("/code", headers=auth_headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["result"]["error"]["code"] == "no_tests_found"
