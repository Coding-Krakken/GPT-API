"""
Comprehensive test suite for GUI Control Layer
Tests Wayland/X11 detection, window management, input automation, and vision capabilities
"""

import pytest
import os
import sys
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Ensure project root is in sys.path for import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from main import app
    from routes.gui_control import detect_gui_session_comprehensive, list_windows_multi_method
    from utils.gui_env import detect_gui_environment_comprehensive
except ImportError as e:
    # Skip tests if dependencies not available
    pytest.skip(f"GUI control dependencies not available: {e}", allow_module_level=True)

API_KEY = os.environ.get("API_KEY", "test-key")
HEADERS = {"x-api-key": API_KEY}
client = TestClient(app)

class TestGuiSessionDetection:
    """Test comprehensive GUI session detection"""
    
    def test_gui_session_endpoint(self):
        """Test /gui/session endpoint"""
        response = client.get("/gui/session", headers=HEADERS)
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify required fields
        assert "session_type" in data
        assert "compositor" in data
        assert "display" in data
        assert "wayland_display" in data
        assert "tools" in data
        assert "capabilities" in data
        assert "detection_methods" in data
        assert "detection_latency_us" in data
        
        # Verify tools structure
        expected_tools = [
            "wmctrl", "xprop", "xwininfo", "xdotool",
            "swaymsg", "wlr-randr", "wayland-info",
            "scrot", "gnome-screenshot", "spectacle",
            "ydotool", "at-spi2-core"
        ]
        
        for tool in expected_tools:
            assert tool in data["tools"]
            assert isinstance(data["tools"][tool], bool)
        
        # Verify capabilities structure
        expected_capabilities = [
            "window_management", "wayland_introspection", "x11_fallback",
            "screenshot", "input_automation", "accessibility"
        ]
        
        for capability in expected_capabilities:
            assert capability in data["capabilities"]
            assert isinstance(data["capabilities"][capability], bool)
    
    @patch('utils.gui_env.shutil.which')
    @patch('os.environ')
    def test_wayland_detection(self, mock_environ, mock_which):
        """Test Wayland session detection"""
        mock_environ.get.side_effect = lambda key, default=None: {
            "WAYLAND_DISPLAY": "wayland-0",
            "XDG_SESSION_TYPE": "wayland",
            "XDG_CURRENT_DESKTOP": "GNOME",
            "GUI_TEST_MODE": None
        }.get(key, default)
        
        mock_which.side_effect = lambda tool: tool in ["swaymsg", "wlr-randr"]
        
        with patch('psutil.process_iter') as mock_proc_iter:
            mock_proc = MagicMock()
            mock_proc.info = {'name': 'gnome-shell'}
            mock_proc_iter.return_value = [mock_proc]
            
            session_info = detect_gui_environment_comprehensive()
            
            assert session_info["session_type"] == "wayland"
            assert session_info["wayland"] is True
            assert session_info["compositor"] == "gnome-shell"
            assert "WAYLAND_DISPLAY_env" in session_info["detection_methods"]
            assert "process_gnome-shell" in session_info["detection_methods"]
    
    @patch('utils.gui_env.shutil.which')
    @patch('os.environ')
    def test_x11_detection(self, mock_environ, mock_which):
        """Test X11 session detection"""
        mock_environ.get.side_effect = lambda key, default=None: {
            "DISPLAY": ":0",
            "XDG_SESSION_TYPE": "x11",
            "GUI_TEST_MODE": None
        }.get(key, default)
        
        mock_which.side_effect = lambda tool: tool in ["wmctrl", "xprop", "xdotool"]
        
        with patch('routes.gui_control.run_with_observability') as mock_run:
            mock_run.return_value = {
                "exit_code": 0,
                "stdout": '_NET_WM_NAME(UTF8_STRING) = "i3"'
            }
            
            session_info = detect_gui_environment_comprehensive()
            
            assert session_info["session_type"] == "x11"
            assert session_info["x11"] is True
            assert session_info["compositor"] == "i3"
            assert session_info["capabilities"]["window_management"] is True

class TestWindowManagement:
    """Test window detection and management"""
    
    @patch('routes.gui_control.get_cached_gui_session')
    @patch('routes.gui_control.run_with_observability')
    def test_list_windows_detailed(self, mock_run, mock_session):
        """Test detailed window listing"""
        mock_session.return_value = {
            "tools": {"wmctrl": True},
            "session_type": "x11"
        }
        
        mock_run.return_value = {
            "exit_code": 0,
            "stdout": "0x02000006  0 12345   100 200 800 600 hostname Firefox\n0x02000007  0 54321   200 300 400 500 hostname Terminal"
        }
        
        response = client.get("/apps_advanced/list_windows_detailed", headers=HEADERS)
        assert response.status_code == 200
        
        data = response.json()
        assert "windows" in data
        assert "methods_tried" in data
        assert "session_info" in data
        assert "latency_us" in data
        
        windows = data["windows"]
        assert len(windows) == 2
        
        # Verify first window structure
        window = windows[0]
        assert window["window_id"] == "0x02000006"
        assert window["pid"] == 12345
        assert window["title"] == "Firefox"
        assert window["geometry"]["x"] == 100
        assert window["geometry"]["y"] == 200
        assert window["geometry"]["width"] == 800
        assert window["geometry"]["height"] == 600
        assert window["method"] == "wmctrl"
    
    @patch('routes.gui_control.get_cached_gui_session')
    @patch('routes.gui_control.run_with_observability')
    def test_swaymsg_window_detection(self, mock_run, mock_session):
        """Test window detection using swaymsg"""
        mock_session.return_value = {
            "tools": {"swaymsg": True},
            "session_type": "wayland"
        }
        
        mock_tree = {
            "id": 1,
            "type": "workspace",
            "nodes": [{
                "id": 123,
                "type": "con",
                "app_id": "firefox",
                "name": "Mozilla Firefox",
                "pid": 12345,
                "focused": True,
                "rect": {"x": 100, "y": 200, "width": 800, "height": 600},
                "nodes": [],
                "floating_nodes": []
            }],
            "floating_nodes": []
        }
        
        mock_run.return_value = {
            "exit_code": 0,
            "stdout": json.dumps(mock_tree)
        }
        
        windows_result = list_windows_multi_method()
        
        assert len(windows_result["windows"]) == 1
        window = windows_result["windows"][0]
        assert window["window_id"] == "123"
        assert window["app_id"] == "firefox"
        assert window["title"] == "Mozilla Firefox"
        assert window["focus"] is True
        assert window["state"] == "focused"
        assert window["method"] == "swaymsg"

class TestWindowActions:
    """Test window control actions"""
    
    @patch('routes.gui_control.get_cached_gui_session')
    @patch('routes.gui_control.list_windows_multi_method')
    @patch('routes.gui_control.run_with_observability')
    def test_focus_window(self, mock_run, mock_list_windows, mock_session):
        """Test window focus action"""
        mock_session.return_value = {
            "tools": {"wmctrl": True},
            "session_type": "x11",
            "capabilities": {"x11_fallback": False}
        }
        
        mock_list_windows.return_value = {
            "windows": [{
                "window_id": "0x02000006",
                "title": "Firefox",
                "geometry": {"x": 100, "y": 200, "width": 800, "height": 600}
            }]
        }
        
        mock_run.return_value = {"exit_code": 0, "stdout": "", "stderr": ""}
        
        response = client.post("/apps_advanced/focus", headers=HEADERS, json={
            "action": "focus",
            "window_id": "0x02000006"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["action"] == "focus"
        assert data["result"]["success"] is True
        assert "wmctrl_output" in data["result"]
    
    @patch('routes.gui_control.get_cached_gui_session')
    @patch('routes.gui_control.list_windows_multi_method')
    @patch('routes.gui_control.run_with_observability')
    def test_resize_window(self, mock_run, mock_list_windows, mock_session):
        """Test window resize action"""
        mock_session.return_value = {
            "tools": {"wmctrl": True},
            "session_type": "x11",
            "capabilities": {"x11_fallback": False}
        }
        
        mock_list_windows.return_value = {
            "windows": [{
                "window_id": "0x02000006",
                "title": "Firefox",
                "geometry": {"x": 100, "y": 200, "width": 800, "height": 600}
            }]
        }
        
        mock_run.return_value = {"exit_code": 0, "stdout": "", "stderr": ""}
        
        response = client.post("/apps_advanced/resize", headers=HEADERS, json={
            "action": "resize",
            "window_id": "0x02000006",
            "x": 150,
            "y": 250,
            "width": 900,
            "height": 700
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["success"] is True
        assert data["result"]["geometry"]["width"] == 900
        assert data["result"]["geometry"]["height"] == 700

class TestInputAutomation:
    """Test input automation capabilities"""
    
    @patch('routes.gui_control.get_cached_gui_session')
    @patch('routes.gui_control.run_with_observability')
    def test_keyboard_input_x11(self, mock_run, mock_session):
        """Test keyboard input via xdotool"""
        mock_session.return_value = {
            "tools": {"xdotool": True},
            "session_type": "x11"
        }
        
        mock_run.return_value = {"exit_code": 0, "stdout": "", "stderr": ""}
        
        response = client.post("/input_enhanced/type", headers=HEADERS, json={
            "action": "type",
            "text": "Hello World"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["action"] == "type"
        assert data["result"]["success"] is True
        assert "xdotool_output" in data["result"]
    
    @patch('routes.gui_control.get_cached_gui_session')
    @patch('routes.gui_control.run_with_observability')
    def test_mouse_click(self, mock_run, mock_session):
        """Test mouse click automation"""
        mock_session.return_value = {
            "tools": {"xdotool": True},
            "session_type": "x11"
        }
        
        mock_run.return_value = {"exit_code": 0, "stdout": "", "stderr": ""}
        
        response = client.post("/input_enhanced/click", headers=HEADERS, json={
            "action": "click",
            "x": 500,
            "y": 300,
            "button": "left"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["success"] is True
        assert data["result"]["coordinates"]["x"] == 500
        assert data["result"]["coordinates"]["y"] == 300

class TestScreenshotCapture:
    """Test screenshot functionality"""
    
    @patch('routes.gui_control.get_cached_gui_session')
    @patch('routes.gui_control.run_with_observability')
    @patch('os.path.exists')
    @patch('os.path.getsize')
    def test_screenshot_capture(self, mock_getsize, mock_exists, mock_run, mock_session):
        """Test screenshot capture"""
        mock_session.return_value = {
            "tools": {"scrot": True},
            "session_type": "x11"
        }
        
        mock_run.return_value = {"exit_code": 0, "stdout": "", "stderr": ""}
        mock_exists.return_value = True
        mock_getsize.return_value = 102400  # 100KB
        
        response = client.post("/apps_advanced/screenshot", headers=HEADERS, json={
            "format": "png"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["success"] is True
        assert data["result"]["format"] == "png"
        assert data["result"]["file_size"] == 102400
        assert "/tmp/screenshot_" in data["result"]["screenshot_path"]

class TestAppLaunching:
    """Test application launching with tracking"""
    
    @patch('subprocess.Popen')
    def test_launch_app_with_tracking(self, mock_popen):
        """Test app launch with PID tracking"""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        
        response = client.post("/apps_advanced/launch", headers=HEADERS, json={
            "app": "firefox",
            "args": "--new-tab https://example.com",
            "workspace": 1
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["status"] == "launched"
        assert data["result"]["pid"] == 12345
        assert data["result"]["app"] == "firefox"
        assert data["result"]["metadata"]["workspace"] == 1

class TestGuiTesting:
    """Test GUI testing capabilities"""
    
    def test_gui_environment_test(self):
        """Test GUI environment testing endpoint"""
        response = client.get("/gui/test", headers=HEADERS)
        assert response.status_code == 200
        
        data = response.json()
        assert "tests" in data
        assert "session_info" in data
        assert "overall_status" in data
        assert "latency_us" in data
        
        # Verify test structure
        tests = data["tests"]
        expected_tests = [
            "session_detection", "window_enumeration", 
            "tool_availability", "fallback_methods"
        ]
        
        for test_name in expected_tests:
            assert test_name in tests
            assert isinstance(tests[test_name], bool)
        
        assert data["overall_status"] in ["healthy", "degraded"]
    
    def test_mock_window_creation(self):
        """Test mock window creation for testing"""
        response = client.post("/apps_advanced/mock_window", headers=HEADERS)
        assert response.status_code == 200
        
        data = response.json()
        assert data["result"]["success"] is True
        
        # Should create either Xvfb window or registry mock
        assert "mock_pid" in data["result"] or "mock_display" in data["result"]

class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_invalid_window_id(self):
        """Test handling of invalid window ID"""
        response = client.post("/apps_advanced/focus", headers=HEADERS, json={
            "action": "focus",
            "window_id": "invalid_id"
        })
        
        assert response.status_code == 404
        data = response.json()
        assert "error" in data["detail"]
        assert data["detail"]["error"]["code"] == "window_not_found"
    
    def test_missing_tools_guidance(self):
        """Test missing tools error handling"""
        with patch('routes.gui_control.get_cached_gui_session') as mock_session:
            mock_session.return_value = {
                "tools": {"wmctrl": False, "xdotool": False},
                "session_type": "x11"
            }
            
            response = client.post("/input_enhanced/type", headers=HEADERS, json={
                "action": "type",
                "text": "test"
            })
            
            assert response.status_code == 200
            data = response.json()
            # Should handle missing tools gracefully
            assert "error" in data["result"]
            assert "no_input_tool" in data["result"]["error"]["code"]

class TestObservability:
    """Test observability and metrics"""
    
    def test_microsecond_precision_timing(self):
        """Test microsecond precision in latency reporting"""
        response = client.get("/gui/session", headers=HEADERS)
        assert response.status_code == 200
        
        data = response.json()
        assert "detection_latency_us" in data
        assert isinstance(data["detection_latency_us"], int)
        assert data["detection_latency_us"] > 0
    
    def test_comprehensive_error_reporting(self):
        """Test structured error reporting"""
        response = client.post("/apps_advanced/resize", headers=HEADERS, json={
            "action": "resize",
            "window_id": "nonexistent"
        })
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert "timestamp" in data["detail"]
        assert "latency_us" in data["detail"]

# Import json for swaymsg tests
import json

if __name__ == "__main__":
    pytest.main([__file__])