import os
import requests
import pytest

API_KEY = os.getenv("API_KEY", "9e2b7c8a-4f1e-4b2a-9d3c-7f6e5a1b2c3d")
BASE_URL = "http://localhost:8000"
HEADERS = {"x-api-key": API_KEY, "Content-Type": "application/json"}

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
    r = requests.post(BASE_URL + "/apps", headers=HEADERS, json=payload)
    # Accept 200 (success) or 404 (window not found) as valid for CI
    assert r.status_code in (200, 404), f"{action} failed: {r.text}"
    if r.status_code == 200:
        assert "result" in r.json()
