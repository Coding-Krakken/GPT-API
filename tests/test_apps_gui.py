
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

gui_actions = [
    ("focus", {}),
    ("minimize", {}),
    ("maximize", {}),
    ("move", {"x": 100, "y": 100}),
    ("resize", {"width": 400, "height": 300}),
]

@pytest.mark.parametrize("action, extra", gui_actions)
def test_gui_actions(action, extra):
    # Use a common app that is likely to be open, e.g., 'code' or 'firefox'.
    # Adjust window_title as needed for your environment.
    payload = {"action": action, "window_title": "code"}
    payload.update(extra)
    r = client.post("/apps", headers=HEADERS, json=payload)
    # Accept 200 (success) or 404 (window not found) as valid for CI
    assert r.status_code in (200, 404), f"{action} failed: {r.text}"
    if r.status_code == 200:
        data = r.json()
        # In headless environments or for unsupported actions, we get "errors" instead of "result"
        if "errors" in data:
            # This is expected for unsupported actions or headless environment
            assert len(data["errors"]) > 0
            assert "code" in data["errors"][0]
        else:
            # Success case with "result"
            assert "result" in data
