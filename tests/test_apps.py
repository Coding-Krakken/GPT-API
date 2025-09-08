import pytest
import os
import platform

class TestAppsEndpoints:
    """Test suite for /apps endpoint operations."""

    def test_capabilities_linux_x11(self, client, auth_headers, monkeypatch):
        """Test capabilities detection for Linux with X11."""
        # Mock Linux environment with X11
        monkeypatch.setattr("platform.system", lambda: "Linux")
        monkeypatch.setattr("shutil.which", lambda cmd: True if cmd in ["wmctrl", "xprop"] else None)
        # Don't override os.environ completely, just set specific keys
        monkeypatch.setattr("os.environ", {**os.environ, "DISPLAY": ":0", "WAYLAND_DISPLAY": None})
        
        response = client.get("/apps/capabilities", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["os"] == "Linux"
        assert data["gui"] is True
        assert data["x11"] is True
        assert data["wayland"] is False
        assert data["window_management"] is True
        assert data["geometry"] is True
        assert data["tools"]["wmctrl"] is True
        assert data["tools"]["xprop"] is True

    def test_capabilities_linux_wayland(self, client, auth_headers, monkeypatch):
        """Test capabilities detection for Linux with Wayland."""
        # Mock Linux environment with Wayland
        monkeypatch.setattr("platform.system", lambda: "Linux")
        monkeypatch.setattr("shutil.which", lambda cmd: True if cmd == "swaymsg" else None)
        monkeypatch.setattr("os.environ", {**os.environ, "DISPLAY": None, "WAYLAND_DISPLAY": "wayland-0"})
        
        response = client.get("/apps/capabilities", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["os"] == "Linux"
        assert data["gui"] is False  # No wmctrl
        assert data["x11"] is False
        assert data["wayland"] is True
        assert data["tools"]["swaymsg"] is True

    def test_capabilities_macos(self, client, auth_headers, monkeypatch):
        """Test capabilities detection for macOS."""
        # Mock macOS environment
        monkeypatch.setattr("platform.system", lambda: "Darwin")
        monkeypatch.setattr("shutil.which", lambda cmd: True if cmd == "osascript" else None)
        
        response = client.get("/apps/capabilities", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["os"] == "Darwin"
        assert data["gui"] is True
        assert data["window_management"] is True
        assert data["multi_window"] is False
        assert data["geometry"] is False
        assert data["tools"]["osascript"] is True

    def test_capabilities_windows(self, client, auth_headers, monkeypatch):
        """Test capabilities detection for Windows."""
        # Mock Windows environment
        monkeypatch.setattr("platform.system", lambda: "Windows")
        monkeypatch.setattr("shutil.which", lambda cmd: True if cmd == "powershell" else None)
        
        response = client.get("/apps/capabilities", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["os"] == "Windows"
        assert data["gui"] is True
        assert data["window_management"] is True
        assert data["multi_window"] is False
        assert data["tools"]["powershell"] is True

    def test_list_apps_empty(self, client, auth_headers):
        """Test listing apps when none are running."""
        payload = {
            "action": "list"
        }
        response = client.post("/apps", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "apps" in data["result"]
        assert isinstance(data["result"]["apps"], list)

    def test_launch_app(self, client, auth_headers):
        """Test launching an app."""
        payload = {
            "action": "launch",
            "app": "echo",
            "args": "test launch"
        }
        response = client.post("/apps", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"]["status"] == "ok"
        assert data["result"]["action"] == "launch"
        assert "pid" in data["result"]
        assert isinstance(data["result"]["pid"], int)

    def test_list_apps_after_launch(self, client, auth_headers):
        """Test listing apps after launching one."""
        # First launch an app
        launch_payload = {
            "action": "launch",
            "app": "echo",
            "args": "test list"
        }
        launch_response = client.post("/apps", headers=auth_headers, json=launch_payload)
        assert launch_response.status_code == 200
        launch_data = launch_response.json()
        pid = launch_data["result"]["pid"]

        # Then list apps
        list_payload = {
            "action": "list"
        }
        list_response = client.post("/apps", headers=auth_headers, json=list_payload)
        assert list_response.status_code == 200
        list_data = list_response.json()

        # Check that the launched app is in the list
        apps = list_data["result"]["apps"]
        assert isinstance(apps, list)
        assert len(apps) > 0

        # Find our app in the list
        our_app = None
        for app in apps:
            if app["pid"] == pid:
                our_app = app
                break

        assert our_app is not None
        assert our_app["app"] == "echo"
        assert our_app["args"] == "test list"
        assert our_app["state"] == "running"

    def test_kill_app(self, client, auth_headers):
        """Test killing an app."""
        # First launch an app
        launch_payload = {
            "action": "launch",
            "app": "echo",
            "args": "test kill"
        }
        launch_response = client.post("/apps", headers=auth_headers, json=launch_payload)
        assert launch_response.status_code == 200
        launch_data = launch_response.json()
        pid = launch_data["result"]["pid"]

        # Then kill it
        kill_payload = {
            "action": "kill",
            "pid": pid
        }
        kill_response = client.post("/apps", headers=auth_headers, json=kill_payload)
        assert kill_response.status_code == 200
        kill_data = kill_response.json()
        assert kill_data["result"]["status"] == "ok"
        assert kill_data["result"]["action"] == "kill"
        assert kill_data["result"]["pid"] == pid

    def test_kill_nonexistent_app(self, client, auth_headers):
        """Test killing a nonexistent app."""
        payload = {
            "action": "kill",
            "pid": 99999
        }
        response = client.post("/apps", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data
        assert len(data["errors"]) > 0
        assert data["errors"][0]["code"] == "NOT_FOUND"

    def test_launch_app_missing_app(self, client, auth_headers):
        """Test launching app with missing app field."""
        payload = {
            "action": "launch",
            "args": "test"
        }
        response = client.post("/apps", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data
        assert len(data["errors"]) > 0
        assert data["errors"][0]["code"] == "MISSING_FIELD"

    def test_kill_app_missing_pid(self, client, auth_headers):
        """Test killing app with missing pid field."""
        payload = {
            "action": "kill"
        }
        response = client.post("/apps", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data
        assert len(data["errors"]) > 0
        assert data["errors"][0]["code"] == "MISSING_FIELD"

    def test_invalid_action(self, client, auth_headers):
        """Test invalid action."""
        payload = {
            "action": "invalid_action"
        }
        response = client.post("/apps", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data
        assert len(data["errors"]) > 0
        assert data["errors"][0]["code"] == "UNSUPPORTED_ACTION"

    def test_missing_action(self, client, auth_headers):
        """Test missing action."""
        payload = {}
        response = client.post("/apps", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data
        assert len(data["errors"]) > 0
        assert data["errors"][0]["code"] == "MISSING_ACTION"

    def test_resize_app(self, client, auth_headers, monkeypatch):
        """Test resizing an app window."""
        # Mock GUI environment by patching the cached env function
        def mock_get_cached_env():
            return {
                "os": "Linux",
                "display": ":0",
                "wayland_display": None,
                "session_type": "x11",
                "wmctrl": True,
                "xprop": True,
                "swaymsg": False,
                "xvfb": False,
                "vnc": False,
                "vnc_display": None,
                "missing_tools": [],
                "test_mode": False,
                "gui": True,
                "x11": True,
                "wayland": False
            }, {
                "DISPLAY": ":0",
                "WAYLAND_DISPLAY": None,
                "XDG_SESSION_TYPE": "x11",
                "os": "Linux",
                "x11": True,
                "wayland": False,
                "wmctrl": True,
                "xprop": True,
                "swaymsg": False,
                "xvfb": False,
                "vnc": False,
                "vnc_display": None,
                "missing_tools": [],
                "test_mode": False
            }
        monkeypatch.setattr("routes.apps._get_cached_env", mock_get_cached_env)
        
        # First launch an app
        launch_payload = {
            "action": "launch",
            "app": "echo",
            "args": "test resize"
        }
        launch_response = client.post("/apps", headers=auth_headers, json=launch_payload)
        assert launch_response.status_code == 200
        launch_data = launch_response.json()
        pid = launch_data["result"]["pid"]

        # Then resize it
        resize_payload = {
            "action": "resize",
            "pid": pid,
            "x": 100,
            "y": 100,
            "width": 800,
            "height": 600
        }
        resize_response = client.post("/apps", headers=auth_headers, json=resize_payload)
        assert resize_response.status_code == 200
        resize_data = resize_response.json()
        assert resize_data["result"]["status"] == "ok"
        assert resize_data["result"]["action"] == "resize"
        assert resize_data["result"]["pid"] == pid

    def test_resize_app_missing_geometry(self, client, auth_headers, monkeypatch):
        """Test resizing app with missing geometry fields."""
        # Mock GUI environment by patching the cached env function
        def mock_get_cached_env():
            return {
                "os": "Linux",
                "display": ":0",
                "wayland_display": None,
                "session_type": "x11",
                "wmctrl": True,
                "xprop": True,
                "swaymsg": False,
                "xvfb": False,
                "vnc": False,
                "vnc_display": None,
                "missing_tools": [],
                "test_mode": False,
                "gui": True,
                "x11": True,
                "wayland": False
            }, {
                "DISPLAY": ":0",
                "WAYLAND_DISPLAY": None,
                "XDG_SESSION_TYPE": "x11",
                "os": "Linux",
                "x11": True,
                "wayland": False,
                "wmctrl": True,
                "xprop": True,
                "swaymsg": False,
                "xvfb": False,
                "vnc": False,
                "vnc_display": None,
                "missing_tools": [],
                "test_mode": False
            }
        monkeypatch.setattr("routes.apps._get_cached_env", mock_get_cached_env)
        
        # First launch an app
        launch_payload = {
            "action": "launch",
            "app": "echo",
            "args": "test resize missing"
        }
        launch_response = client.post("/apps", headers=auth_headers, json=launch_payload)
        assert launch_response.status_code == 200
        launch_data = launch_response.json()
        pid = launch_data["result"]["pid"]

        # Try to resize with missing fields
        resize_payload = {
            "action": "resize",
            "pid": pid,
            "x": 100,
            "y": 100
            # Missing width and height
        }
        resize_response = client.post("/apps", headers=auth_headers, json=resize_payload)
        assert resize_response.status_code == 200
        resize_data = resize_response.json()
        assert "errors" in resize_data
        assert len(resize_data["errors"]) > 0
        assert resize_data["errors"][0]["code"] == "MISSING_FIELD"

    def test_resize_app_invalid_geometry(self, client, auth_headers, monkeypatch):
        """Test resizing app with invalid geometry values."""
        # Mock GUI environment by patching the cached env function
        def mock_get_cached_env():
            return {
                "os": "Linux",
                "display": ":0",
                "wayland_display": None,
                "session_type": "x11",
                "wmctrl": True,
                "xprop": True,
                "swaymsg": False,
                "xvfb": False,
                "vnc": False,
                "vnc_display": None,
                "missing_tools": [],
                "test_mode": False,
                "gui": True,
                "x11": True,
                "wayland": False
            }, {
                "DISPLAY": ":0",
                "WAYLAND_DISPLAY": None,
                "XDG_SESSION_TYPE": "x11",
                "os": "Linux",
                "x11": True,
                "wayland": False,
                "wmctrl": True,
                "xprop": True,
                "swaymsg": False,
                "xvfb": False,
                "vnc": False,
                "vnc_display": None,
                "missing_tools": [],
                "test_mode": False
            }
        monkeypatch.setattr("routes.apps._get_cached_env", mock_get_cached_env)
        
        # First launch an app
        launch_payload = {
            "action": "launch",
            "app": "echo",
            "args": "test resize invalid"
        }
        launch_response = client.post("/apps", headers=auth_headers, json=launch_payload)
        assert launch_response.status_code == 200
        launch_data = launch_response.json()
        pid = launch_data["result"]["pid"]

        # Try to resize with invalid values
        resize_payload = {
            "action": "resize",
            "pid": pid,
            "x": -100,
            "y": -100,
            "width": 0,
            "height": 0
        }
        resize_response = client.post("/apps", headers=auth_headers, json=resize_payload)
        assert resize_response.status_code == 200
        resize_data = resize_response.json()
        assert "errors" in resize_data
        assert len(resize_data["errors"]) > 0
        assert resize_data["errors"][0]["code"] == "INVALID_GEOMETRY"

    def test_resize_nonexistent_app(self, client, auth_headers, monkeypatch):
        """Test resizing a nonexistent app."""
        # Mock GUI environment by patching the cached env function
        def mock_get_cached_env():
            return {
                "os": "Linux",
                "display": ":0",
                "wayland_display": None,
                "session_type": "x11",
                "wmctrl": True,
                "xprop": True,
                "swaymsg": False,
                "xvfb": False,
                "vnc": False,
                "vnc_display": None,
                "missing_tools": [],
                "test_mode": False,
                "gui": True,
                "x11": True,
                "wayland": False
            }, {
                "DISPLAY": ":0",
                "WAYLAND_DISPLAY": None,
                "XDG_SESSION_TYPE": "x11",
                "os": "Linux",
                "x11": True,
                "wayland": False,
                "wmctrl": True,
                "xprop": True,
                "swaymsg": False,
                "xvfb": False,
                "vnc": False,
                "vnc_display": None,
                "missing_tools": [],
                "test_mode": False
            }
        monkeypatch.setattr("routes.apps._get_cached_env", mock_get_cached_env)
        
        payload = {
            "action": "resize",
            "pid": 99999,
            "x": 100,
            "y": 100,
            "width": 800,
            "height": 600
        }
        response = client.post("/apps", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data
        assert len(data["errors"]) > 0
        assert data["errors"][0]["code"] == "NOT_FOUND"

    def test_move_app(self, client, auth_headers, monkeypatch):
        """Test moving an app window."""
        # Mock GUI environment by patching the cached env function
        def mock_get_cached_env():
            return {
                "os": "Linux",
                "display": ":0",
                "wayland_display": None,
                "session_type": "x11",
                "wmctrl": True,
                "xprop": True,
                "swaymsg": False,
                "xvfb": False,
                "vnc": False,
                "vnc_display": None,
                "missing_tools": [],
                "test_mode": False,
                "gui": True,
                "x11": True,
                "wayland": False
            }, {
                "DISPLAY": ":0",
                "WAYLAND_DISPLAY": None,
                "XDG_SESSION_TYPE": "x11",
                "os": "Linux",
                "x11": True,
                "wayland": False,
                "wmctrl": True,
                "xprop": True,
                "swaymsg": False,
                "xvfb": False,
                "vnc": False,
                "vnc_display": None,
                "missing_tools": [],
                "test_mode": False
            }
        monkeypatch.setattr("routes.apps._get_cached_env", mock_get_cached_env)
        
        # First launch an app
        launch_payload = {
            "action": "launch",
            "app": "echo",
            "args": "test move"
        }
        launch_response = client.post("/apps", headers=auth_headers, json=launch_payload)
        assert launch_response.status_code == 200
        launch_data = launch_response.json()
        pid = launch_data["result"]["pid"]

        # Then move it
        move_payload = {
            "action": "move",
            "pid": pid,
            "x": 200,
            "y": 200,
            "width": 400,
            "height": 300
        }
        move_response = client.post("/apps", headers=auth_headers, json=move_payload)
        assert move_response.status_code == 200
        move_data = move_response.json()
        assert move_data["result"]["status"] == "ok"
        assert move_data["result"]["action"] == "move"
        assert move_data["result"]["pid"] == pid

    def test_list_windows_missing_tools(self, client, auth_headers, monkeypatch):
        """Test list_windows with missing tools."""
        # Mock environment with missing tools and ensure not in test mode
        def mock_get_cached_env():
            return {
                "os": "Linux",
                "display": ":0",
                "wayland_display": None,
                "session_type": "x11",
                "wmctrl": False,
                "xprop": False,
                "swaymsg": False,
                "xvfb": False,
                "vnc": False,
                "vnc_display": None,
                "missing_tools": ["wmctrl", "xprop"],
                "test_mode": False,  # Ensure not in test mode
                "gui": True,
                "x11": True,
                "wayland": False
            }, {
                "DISPLAY": ":0",
                "WAYLAND_DISPLAY": None,
                "XDG_SESSION_TYPE": "x11",
                "os": "Linux",
                "x11": True,
                "wayland": False,
                "wmctrl": False,
                "xprop": False,
                "swaymsg": False,
                "xvfb": False,
                "vnc": False,
                "vnc_display": None,
                "missing_tools": ["wmctrl", "xprop"],
                "test_mode": False
            }
        
        def mock_environ_get(key, default=None):
            if key == "PATH":
                return ""  # Empty PATH so tools are missing
            elif key == "GUI_TEST_MODE":
                return None  # Not in test mode
            elif key == "PYTHONASYNCIODEBUG":
                return None  # Avoid recursion in asyncio
            elif key == "API_KEY":
                return "9e2b7c8a-4f1e-4b2a-9d3c-7f6e5a1b2c3d"  # Preserve API key for auth
            # For other keys, return the default
            return default
        
        monkeypatch.setattr("routes.apps._get_cached_env", mock_get_cached_env)
        monkeypatch.setattr("os.environ.get", mock_environ_get)
        
        payload = {"action": "list_windows"}
        response = client.post("/apps", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data
        assert data["errors"][0]["code"] == "MISSING_TOOLS"

    def test_list_windows_with_tools(self, client, auth_headers, monkeypatch):
        """Test list_windows with available tools."""
        # Mock environment with available tools
        def mock_get_cached_env():
            return {
                "os": "Linux",
                "display": ":0",
                "wayland_display": None,
                "session_type": "x11",
                "wmctrl": True,
                "xprop": True,
                "swaymsg": False,
                "xvfb": False,
                "vnc": False,
                "vnc_display": None,
                "missing_tools": [],
                "test_mode": False,
                "gui": True,
                "x11": True,
                "wayland": False
            }, {
                "DISPLAY": ":0",
                "WAYLAND_DISPLAY": None,
                "XDG_SESSION_TYPE": "x11",
                "os": "Linux",
                "x11": True,
                "wayland": False,
                "wmctrl": True,
                "xprop": True,
                "swaymsg": False,
                "xvfb": False,
                "vnc": False,
                "vnc_display": None,
                "missing_tools": [],
                "test_mode": False
            }
        monkeypatch.setattr("routes.apps._get_cached_env", mock_get_cached_env)
        
        payload = {"action": "list_windows"}
        response = client.post("/apps", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "windows" in data["result"]

    def test_launch_app_validation(self, client, auth_headers):
        """Test various launch app validation scenarios."""
        # Test missing app
        payload = {"action": "launch", "args": "test"}
        response = client.post("/apps", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data
        assert data["errors"][0]["code"] == "MISSING_FIELD"

        # Test invalid app name
        payload = {"action": "launch", "app": "bad;app", "args": "test"}
        response = client.post("/apps", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data
        assert data["errors"][0]["code"] == "INVALID_APP"

        # Test dangerous args
        payload = {"action": "launch", "app": "echo", "args": "; rm -rf /"}
        response = client.post("/apps", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data
        assert data["errors"][0]["code"] == "DANGEROUS_ARGS"

    def test_kill_app_validation(self, client, auth_headers):
        """Test kill app validation."""
        # Test missing pid
        payload = {"action": "kill"}
        response = client.post("/apps", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data
        assert data["errors"][0]["code"] == "MISSING_FIELD"

    def test_geometry_operations_validation(self, client, auth_headers, monkeypatch):
        """Test geometry operations validation."""
        # Mock GUI environment by patching the cached env function
        def mock_get_cached_env():
            return {
                "os": "Linux",
                "display": ":0",
                "wayland_display": None,
                "session_type": "x11",
                "wmctrl": True,
                "xprop": True,
                "swaymsg": False,
                "xvfb": False,
                "vnc": False,
                "vnc_display": None,
                "missing_tools": [],
                "test_mode": False,
                "gui": True,
                "x11": True,
                "wayland": False
            }, {
                "DISPLAY": ":0",
                "WAYLAND_DISPLAY": None,
                "XDG_SESSION_TYPE": "x11",
                "os": "Linux",
                "x11": True,
                "wayland": False,
                "wmctrl": True,
                "xprop": True,
                "swaymsg": False,
                "xvfb": False,
                "vnc": False,
                "vnc_display": None,
                "missing_tools": [],
                "test_mode": False
            }
        monkeypatch.setattr("routes.apps._get_cached_env", mock_get_cached_env)
        
        # Test missing pid
        payload = {"action": "resize", "x": 100, "y": 100, "width": 800, "height": 600}
        response = client.post("/apps", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data
        assert data["errors"][0]["code"] == "MISSING_FIELD"

        # Test missing geometry fields
        payload = {"action": "resize", "pid": 12345, "x": 100, "y": 100}
        response = client.post("/apps", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data
        assert data["errors"][0]["code"] == "MISSING_FIELD"

        # Test invalid geometry
        payload = {"action": "resize", "pid": 12345, "x": -100, "y": -100, "width": 0, "height": 0}
        response = client.post("/apps", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data
        assert data["errors"][0]["code"] == "INVALID_GEOMETRY"

    def test_headless_geometry_operations(self, client, auth_headers, monkeypatch):
        """Test geometry operations in headless environment."""
        # Mock headless environment
        def mock_get_cached_env():
            return {
                "os": "Linux",
                "display": None,
                "wayland_display": None,
                "session_type": None,
                "wmctrl": False,
                "xprop": False,
                "swaymsg": False,
                "xvfb": False,
                "vnc": False,
                "vnc_display": None,
                "missing_tools": [],
                "test_mode": False,
                "gui": False,
                "x11": False,
                "wayland": False
            }, {
                "DISPLAY": None,
                "WAYLAND_DISPLAY": None,
                "XDG_SESSION_TYPE": None,
                "os": "Linux",
                "x11": False,
                "wayland": False,
                "wmctrl": False,
                "xprop": False,
                "swaymsg": False,
                "xvfb": False,
                "vnc": False,
                "vnc_display": None,
                "missing_tools": [],
                "test_mode": False
            }
        monkeypatch.setattr("routes.apps._get_cached_env", mock_get_cached_env)
        
        # First launch an app
        launch_payload = {"action": "launch", "app": "echo", "args": "test"}
        launch_response = client.post("/apps", headers=auth_headers, json=launch_payload)
        assert launch_response.status_code == 200
        pid = launch_response.json()["result"]["pid"]

        # Try geometry operation in headless mode
        resize_payload = {"action": "resize", "pid": pid, "x": 100, "y": 100, "width": 800, "height": 600}
        resize_response = client.post("/apps", headers=auth_headers, json=resize_payload)
        assert resize_response.status_code == 200
        data = resize_response.json()
        assert "errors" in data
        assert data["errors"][0]["code"] == "HEADLESS_ENVIRONMENT"

    def test_dangerous_app_name(self, client, auth_headers):
        """Test launching app with dangerous name."""
        payload = {
            "action": "launch",
            "app": "rm -rf /",
            "args": ""
        }
        response = client.post("/apps", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data
        assert len(data["errors"]) > 0
        assert data["errors"][0]["code"] == "INVALID_APP"

    def test_dangerous_args(self, client, auth_headers):
        """Test launching app with dangerous arguments."""
        payload = {
            "action": "launch",
            "app": "echo",
            "args": "; rm -rf /"
        }
        response = client.post("/apps", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data
        assert len(data["errors"]) > 0
        assert data["errors"][0]["code"] == "DANGEROUS_ARGS"

    def test_headless_environment_error(self, client, auth_headers):
        """Test operations that require GUI in headless environment."""
        # This test may pass or fail depending on environment
        # In headless environments, GUI operations should fail gracefully
        payload = {
            "action": "resize",
            "pid": 12345,
            "x": 100,
            "y": 100,
            "width": 800,
            "height": 600
        }
        response = client.post("/apps", headers=auth_headers, json=payload)
        # Should either succeed (if GUI available) or fail gracefully
        assert response.status_code == 200
        data = response.json()
        # Either success or expected error
        if "errors" in data:
            assert isinstance(data["errors"], list)

    def test_app_lifecycle(self, client, auth_headers, monkeypatch):
        """Test complete app lifecycle: launch, list, resize, kill."""
        # Mock GUI environment by patching the cached env function
        def mock_get_cached_env():
            return {
                "os": "Linux",
                "display": ":0",
                "wayland_display": None,
                "session_type": "x11",
                "wmctrl": True,
                "xprop": True,
                "swaymsg": False,
                "xvfb": False,
                "vnc": False,
                "vnc_display": None,
                "missing_tools": [],
                "test_mode": False,
                "gui": True,
                "x11": True,
                "wayland": False
            }, {
                "DISPLAY": ":0",
                "WAYLAND_DISPLAY": None,
                "XDG_SESSION_TYPE": "x11",
                "os": "Linux",
                "x11": True,
                "wayland": False,
                "wmctrl": True,
                "xprop": True,
                "swaymsg": False,
                "xvfb": False,
                "vnc": False,
                "vnc_display": None,
                "missing_tools": [],
                "test_mode": False
            }
        monkeypatch.setattr("routes.apps._get_cached_env", mock_get_cached_env)
        
        # Launch
        launch_payload = {
            "action": "launch",
            "app": "echo",
            "args": "lifecycle test"
        }
        launch_response = client.post("/apps", headers=auth_headers, json=launch_payload)
        assert launch_response.status_code == 200
        launch_data = launch_response.json()
        pid = launch_data["result"]["pid"]

        # List and verify
        list_payload = {"action": "list"}
        list_response = client.post("/apps", headers=auth_headers, json=list_payload)
        assert list_response.status_code == 200
        list_data = list_response.json()
        apps = list_data["result"]["apps"]
        our_app = next((app for app in apps if app["pid"] == pid), None)
        assert our_app is not None
        assert our_app["state"] == "running"

        # Resize
        resize_payload = {
            "action": "resize",
            "pid": pid,
            "x": 50,
            "y": 50,
            "width": 640,
            "height": 480
        }
        resize_response = client.post("/apps", headers=auth_headers, json=resize_payload)
        assert resize_response.status_code == 200

        # Kill
        kill_payload = {"action": "kill", "pid": pid}
        kill_response = client.post("/apps", headers=auth_headers, json=kill_payload)
        assert kill_response.status_code == 200

        # Verify killed
        list_response2 = client.post("/apps", headers=auth_headers, json=list_payload)
        assert list_response2.status_code == 200
        list_data2 = list_response2.json()
        apps2 = list_data2["result"]["apps"]
        our_app2 = next((app for app in apps2 if app["pid"] == pid), None)
        if our_app2:
            assert our_app2["state"] == "terminated"