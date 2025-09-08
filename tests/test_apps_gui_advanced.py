
import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure project root is in sys.path for import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from main import app

API_KEY = os.environ.get("API_KEY", "test-key")
HEADERS = {"x-api-key": API_KEY}
client = TestClient(app)

def test_missing_tools_guidance():
    # Simulate missing tools by patching PATH
    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = ""
    payload = {"action": "list_windows"}
    r = client.post("/apps", headers=HEADERS, json=payload)
    os.environ["PATH"] = old_path
    assert r.status_code == 500
    data = r.json()
    assert data["error"] == "MissingTools"
    assert "Install with" in data["detail"]
    assert "missing_tools" in data
    assert "env" in data

def test_env_logging_and_fallback():
    payload = {"action": "list_windows"}
    r = client.post("/apps", headers=HEADERS, json=payload)
    data = r.json()
    assert "env" in data
    if "fallback_attempted" in data:
        assert isinstance(data["fallback_attempted"], bool)

def test_headless_mode(monkeypatch):
    monkeypatch.setenv("GUI_TEST_MODE", "1")
    payload = {"action": "list_windows"}
    r = client.post("/apps", headers=HEADERS, json=payload)
    data = r.json()
    assert "env" in data
    assert data["env"].get("test_mode") is True
    monkeypatch.delenv("GUI_TEST_MODE", raising=False)
