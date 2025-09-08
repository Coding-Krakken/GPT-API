import os
import pytest

def test_code_content_supported_actions(client, auth_headers):
    # Supported actions for content: run, test, lint, fix, format
    code = "print('hello')\n"
    for action in ["run", "test", "lint", "fix", "format"]:
        payload = {"action": action, "content": code, "language": "python"}
        response = client.post("/code", headers=auth_headers, json=payload)
        # Accept 200 or 400 (e.g., lint/fix/format may fail if tools not installed)
        assert response.status_code in (200, 400), f"{action} with content failed: {response.text}"

def test_code_content_unsupported_action(client, auth_headers):
    # 'explain' does not support content
    code = "print('explain')\n"
    payload = {"action": "explain", "content": code, "language": "python"}
    response = client.post("/code", headers=auth_headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["result"]["error"]["code"] == "unsupported_content"

def test_code_content_and_path_missing(client, auth_headers):
    # Should fail if neither path nor content is provided
    payload = {"action": "run", "language": "python"}
    response = client.post("/code", headers=auth_headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["result"]["error"]["code"] == "missing_path_or_content"

def test_code_content_invalid_language(client, auth_headers):
    # Should fail for unsupported language
    payload = {"action": "run", "content": "print(1)", "language": "ruby"}
    response = client.post("/code", headers=auth_headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["result"]["error"]["code"] == "unsupported_language"

def test_code_content_fuzz(client, auth_headers):
    # Fuzz with random/invalid content
    import random, string
    for _ in range(5):
        fuzz_content = ''.join(random.choices(string.printable, k=100))
        payload = {"action": "run", "content": fuzz_content, "language": "python"}
        response = client.post("/code", headers=auth_headers, json=payload)
        assert response.status_code in (200, 400), f"Fuzz run failed: {response.text}"
