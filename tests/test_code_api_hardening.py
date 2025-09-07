import os
import requests
import pytest
import threading
import time

API_KEY = os.getenv("API_KEY", "9e2b7c8a-4f1e-4b2a-9d3c-7f6e5a1b2c3d")
BASE_URL = "http://localhost:8000"
HEADERS = {"x-api-key": API_KEY, "Content-Type": "application/json"}

def test_code_run_invalid_language():
    payload = {"action": "run", "path": "test_code_endpoint.py", "language": "invalid_lang"}
    r = requests.post(BASE_URL + "/code", headers=HEADERS, json=payload)
    assert r.status_code == 400
    data = r.json()
    assert data["error"]["code"] == "unsupported_language"

def test_code_run_concurrent():
    # Create a temp file for concurrency test
    fname = "concurrent_test.py"
    with open(fname, "w") as f:
        f.write("print('concurrent')\n")
    payload = {"action": "run", "path": fname, "language": "python"}
    results = []
    def run_code():
        r = requests.post(BASE_URL + "/code", headers=HEADERS, json=payload)
        results.append(r.status_code)
    threads = [threading.Thread(target=run_code) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # At least one should succeed, others may get 429 (concurrent_access)
    assert 200 in results
    assert any(code == 429 for code in results)
    os.remove(fname)

def test_code_path_injection():
    payload = {"action": "run", "path": "../etc/passwd", "language": "python"}
    r = requests.post(BASE_URL + "/code", headers=HEADERS, json=payload)
    assert r.status_code == 400
    data = r.json()
    assert data["error"]["code"] == "invalid_path"

def test_code_path_too_long():
    long_path = "a" * 300 + ".py"
    payload = {"action": "run", "path": long_path, "language": "python"}
    r = requests.post(BASE_URL + "/code", headers=HEADERS, json=payload)
    assert r.status_code == 400
    data = r.json()
    assert data["error"]["code"] == "path_too_long"

def test_code_no_tests_found():
    fname = "no_tests.py"
    with open(fname, "w") as f:
        f.write("print('no tests')\n")
    payload = {"action": "test", "path": fname, "language": "python"}
    r = requests.post(BASE_URL + "/code", headers=HEADERS, json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["error"]["code"] == "no_tests_found"
    os.remove(fname)
