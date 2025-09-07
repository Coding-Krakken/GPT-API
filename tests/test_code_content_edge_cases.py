import os
import requests
import pytest

API_KEY = os.getenv("API_KEY", "9e2b7c8a-4f1e-4b2a-9d3c-7f6e5a1b2c3d")
BASE_URL = "http://localhost:8000"
HEADERS = {"x-api-key": API_KEY, "Content-Type": "application/json"}

def test_code_content_supported_actions():
    # Supported actions for content: run, test, lint, fix, format
    code = "print('hello')\n"
    for action in ["run", "test", "lint", "fix", "format"]:
        payload = {"action": action, "content": code, "language": "python"}
        r = requests.post(BASE_URL + "/code", headers=HEADERS, json=payload)
        # Accept 200 or 400 (e.g., lint/fix/format may fail if tools not installed)
        assert r.status_code in (200, 400), f"{action} with content failed: {r.text}"

def test_code_content_unsupported_action():
    # 'explain' does not support content
    code = "print('explain')\n"
    payload = {"action": "explain", "content": code, "language": "python"}
    r = requests.post(BASE_URL + "/code", headers=HEADERS, json=payload)
    assert r.status_code == 400
    data = r.json()
    assert data["error"]["code"] == "unsupported_content"

def test_code_content_and_path_missing():
    # Should fail if neither path nor content is provided
    payload = {"action": "run", "language": "python"}
    r = requests.post(BASE_URL + "/code", headers=HEADERS, json=payload)
    assert r.status_code == 400
    data = r.json()
    assert data["error"]["code"] == "missing_path_or_content"

def test_code_content_invalid_language():
    # Should fail for unsupported language
    payload = {"action": "run", "content": "print(1)", "language": "ruby"}
    r = requests.post(BASE_URL + "/code", headers=HEADERS, json=payload)
    assert r.status_code == 400
    data = r.json()
    assert data["error"]["code"] == "unsupported_language"

def test_code_content_fuzz():
    # Fuzz with random/invalid content
    import random, string
    for _ in range(5):
        fuzz_content = ''.join(random.choices(string.printable, k=100))
        payload = {"action": "run", "content": fuzz_content, "language": "python"}
        r = requests.post(BASE_URL + "/code", headers=HEADERS, json=payload)
        assert r.status_code in (200, 400), f"Fuzz run failed: {r.text}"
