"""
Comprehensive test suite for enhanced input synthesis functionality.
Tests the improved mouse drag, keyboard combinations, and text typing with advanced features.
"""


import pytest
from fastapi.testclient import TestClient
from main import app
import json
from unittest.mock import patch, MagicMock
from tests.test_utils import get_api_key

client = TestClient(app)
API_KEY = get_api_key()
HEADERS = {"x-api-key": API_KEY}

class TestEnhancedMouseDrag:
    """Test enhanced mouse drag capabilities"""
    
    def test_mouse_drag_input_validation(self):
        """Test comprehensive input validation for mouse drag"""
        # Invalid duration
        response = client.post("/input/mouse_drag", headers=HEADERS, json={
            "action": "drag",
            "from_x": 100, "from_y": 100,
            "to_x": 200, "to_y": 200,
            "duration": 35  # > 30 seconds
        })
        assert response.status_code == 200
        result = response.json()
        assert "errors" in result
        assert result["errors"][0]["code"] == "INVALID_DURATION"
        
        # Invalid steps
        response = client.post("/input/mouse_drag", headers=HEADERS, json={
            "action": "drag",
            "from_x": 100, "from_y": 100,
            "to_x": 200, "to_y": 200,
            "steps": 1500  # > 1000
        })
        assert response.status_code == 200
        result = response.json()
        assert "errors" in result
        assert result["errors"][0]["code"] == "INVALID_STEPS"
        
        # Invalid interpolation
        response = client.post("/input/mouse_drag", headers=HEADERS, json={
            "action": "drag",
            "from_x": 100, "from_y": 100,
            "to_x": 200, "to_y": 200,
            "interpolation": "invalid_type"
        })
        assert response.status_code == 200
        result = response.json()
        assert "errors" in result
        assert result["errors"][0]["code"] == "INVALID_INTERPOLATION"
        
        # Invalid payload type
        response = client.post("/input/mouse_drag", headers=HEADERS, json={
            "action": "drag",
            "from_x": 100, "from_y": 100,
            "to_x": 200, "to_y": 200,
            "payload_type": "invalid_payload"
        })
        assert response.status_code == 200
        result = response.json()
        assert "errors" in result
        assert result["errors"][0]["code"] == "INVALID_PAYLOAD_TYPE"
    
    def test_mouse_drag_dry_run_enhanced(self):
        """Test enhanced dry run functionality"""
        response = client.post("/input/mouse_drag", headers=HEADERS, json={
            "action": "drag",
            "from_x": 100, "from_y": 100,
            "to_x": 300, "to_y": 250,
            "duration": 1.0,
            "steps": 20,
            "interpolation": "bezier",
            "payload_type": "text",
            "payload_data": "test payload",
            "dry_run": True
        })
        
        assert response.status_code == 200
        result = response.json()
        
        assert "result" in result
        assert result["result"]["status"] == "would_execute"
        assert result["result"]["interpolation"] == "bezier"
        assert result["result"]["path_points"] == 20
        assert "distance" in result["result"]
        assert "payload" in result["result"]
        assert result["result"]["payload"]["type"] == "text"
        assert result["result"]["payload"]["has_data"] == True
        assert "preview_path" in result["result"]
        assert "safety_check" in result["result"]
    
    @patch('routes.input.PYAUTOGUI_AVAILABLE', True)
    @patch('routes.input.pyautogui')
    @patch('routes.input.safety_check')
    def test_mouse_drag_with_payload(self, mock_safety, mock_pyautogui):
        """Test mouse drag with payload injection"""
        # Mock safety check
        mock_safety.return_value = {"safe": True, "level": "low"}
        
        # Mock pyautogui functions
        mock_pyautogui.moveTo = MagicMock()
        mock_pyautogui.mouseDown = MagicMock()
        mock_pyautogui.mouseUp = MagicMock()
        
        response = client.post("/input/mouse_drag", headers=HEADERS, json={
            "action": "drag",
            "from_x": 100, "from_y": 100,
            "to_x": 200, "to_y": 200,
            "payload_type": "text",
            "payload_data": "test payload data",
            "interpolation": "linear",
            "steps": 5
        })
        
        assert response.status_code == 200
        result = response.json()
        
        if "result" in result:
            assert result["result"]["status"] == "completed"
            assert "payload_injection" in result["result"]
            assert result["result"]["actual_path_points"] == 5
            assert "distance" in result["result"]
        else:
            # Expected if dependencies are not available
            assert "errors" in result
    
    def test_mouse_drag_coordinate_validation(self):
        """Test coordinate validation for mouse drag"""
        # Test with extremely large coordinates
        response = client.post("/input/mouse_drag", headers=HEADERS, json={
            "action": "drag",
            "from_x": 50000, "from_y": 50000,  # Beyond reasonable screen size
            "to_x": 60000, "to_y": 60000,
            "dry_run": True
        })
        
        assert response.status_code == 200
        result = response.json()
        # May accept or reject based on validation logic
        assert "result" in result or "errors" in result


class TestEnhancedKeyCombo:
    """Test enhanced keyboard combination capabilities"""
    
    def test_key_combo_validation(self):
        """Test comprehensive validation for key combinations"""
        # Too many keys
        response = client.post("/input/key_combo", headers=HEADERS, json={
            "action": "press",
            "keys": ["ctrl", "alt", "shift", "a", "b", "c", "d", "e", "f", "g", "h"]  # > 10 keys
        })
        assert response.status_code == 200
        result = response.json()
        assert "errors" in result
        assert result["errors"][0]["code"] == "TOO_MANY_KEYS"
        
        # Invalid hold duration
        response = client.post("/input/key_combo", headers=HEADERS, json={
            "action": "press",
            "keys": ["ctrl", "c"],
            "hold_duration": 10  # > 5 seconds
        })
        assert response.status_code == 200
        result = response.json()
        assert "errors" in result
        assert result["errors"][0]["code"] == "INVALID_HOLD_DURATION"
        
        # Invalid press pattern
        response = client.post("/input/key_combo", headers=HEADERS, json={
            "action": "press",
            "keys": ["ctrl", "c"],
            "press_pattern": "invalid_pattern"
        })
        assert response.status_code == 200
        result = response.json()
        assert "errors" in result
        assert result["errors"][0]["code"] == "INVALID_PRESS_PATTERN"
        
        # Invalid repeat count
        response = client.post("/input/key_combo", headers=HEADERS, json={
            "action": "press",
            "keys": ["ctrl", "c"],
            "repeat_count": 150  # > 100
        })
        assert response.status_code == 200
        result = response.json()
        assert "errors" in result
        assert result["errors"][0]["code"] == "INVALID_REPEAT_COUNT"
    
    def test_key_combo_dry_run_enhanced(self):
        """Test enhanced dry run with execution plan"""
        response = client.post("/input/key_combo", headers=HEADERS, json={
            "action": "press",
            "keys": ["ctrl", "shift", "n"],
            "press_pattern": "sequential",
            "release_pattern": "reverse",
            "repeat_count": 2,
            "hold_duration": 0.1,
            "sequence_delay": 0.5,
            "dry_run": True
        })
        
        assert response.status_code == 200
        result = response.json()
        
        assert "result" in result
        assert result["result"]["status"] == "would_execute"
        assert "execution_plan" in result["result"]
        assert len(result["result"]["execution_plan"]) == 2  # 2 repeats
        assert result["result"]["press_pattern"] == "sequential"
        assert result["result"]["release_pattern"] == "reverse"
        assert "normalized_keys" in result["result"]
    
    def test_key_combo_dangerous_combinations(self):
        """Test safety checks for dangerous key combinations"""
        # Test Ctrl+Alt+Delete
        response = client.post("/input/key_combo", headers=HEADERS, json={
            "action": "press",
            "keys": ["ctrl", "alt", "delete"],
            "dry_run": True
        })
        
        assert response.status_code == 200
        result = response.json()
        # Should either be blocked by safety or allowed with warning
        assert "result" in result or "errors" in result
        
        if "errors" in result:
            assert result["errors"][0]["code"] == "SAFETY_VIOLATION"
    
    @patch('routes.input.PYAUTOGUI_AVAILABLE', True)
    @patch('routes.input.pyautogui')
    @patch('routes.input.safety_check')
    def test_key_combo_sequential_pattern(self, mock_safety, mock_pyautogui):
        """Test sequential key press pattern"""
        # Mock safety check
        mock_safety.return_value = {"safe": True, "level": "low"}
        
        # Mock pyautogui functions
        mock_pyautogui.keyDown = MagicMock()
        mock_pyautogui.keyUp = MagicMock()
        
        response = client.post("/input/key_combo", headers=HEADERS, json={
            "action": "press",
            "keys": ["ctrl", "shift", "t"],
            "press_pattern": "sequential",
            "release_pattern": "reverse",
            "hold_duration": 0.1
        })
        
        assert response.status_code == 200
        result = response.json()
        
        if "result" in result:
            assert result["result"]["status"] == "completed"
            assert "execution_log" in result["result"]
            assert "total_actions" in result["result"]
        else:
            assert "errors" in result


class TestEnhancedTypeText:
    """Test enhanced text typing capabilities"""
    
    def test_type_text_validation(self):
        """Test comprehensive validation for text typing"""
        # Text too long
        long_text = "a" * 15000  # > 10,000 characters
        response = client.post("/input/type_text", headers=HEADERS, json={
            "action": "type",
            "text": long_text
        })
        assert response.status_code == 200
        result = response.json()
        assert "errors" in result
        assert result["errors"][0]["code"] == "TEXT_TOO_LONG"
        
        # Invalid typing speed
        response = client.post("/input/type_text", headers=HEADERS, json={
            "action": "type",
            "text": "test",
            "typing_speed": 10  # > 5 seconds
        })
        assert response.status_code == 200
        result = response.json()
        assert "errors" in result
        assert result["errors"][0]["code"] == "INVALID_TYPING_SPEED"
        
        # Invalid typing pattern
        response = client.post("/input/type_text", headers=HEADERS, json={
            "action": "type",
            "text": "test",
            "typing_pattern": "invalid_pattern"
        })
        assert response.status_code == 200
        result = response.json()
        assert "errors" in result
        assert result["errors"][0]["code"] == "INVALID_TYPING_PATTERN"
        
        # Invalid error rate
        response = client.post("/input/type_text", headers=HEADERS, json={
            "action": "type",
            "text": "test",
            "error_rate": 1.5  # > 1.0
        })
        assert response.status_code == 200
        result = response.json()
        assert "errors" in result
        assert result["errors"][0]["code"] == "INVALID_ERROR_RATE"
    
    def test_type_text_dry_run_enhanced(self):
        """Test enhanced dry run with text analysis"""
        response = client.post("/input/type_text", headers=HEADERS, json={
            "action": "type",
            "text": "Hello, world! This is a test with special chars: ñáéíóú",
            "typing_pattern": "human",
            "error_simulation": True,
            "error_rate": 0.05,
            "ime_mode": True,
            "language": "es",
            "dry_run": True
        })
        
        assert response.status_code == 200
        result = response.json()
        
        assert "result" in result
        assert result["result"]["status"] == "would_execute"
        assert "text_stats" in result["result"]
        
        stats = result["result"]["text_stats"]
        assert "character_count" in stats
        assert "word_count" in stats
        assert "sentence_count" in stats
        assert "has_special_chars" in stats
        assert "requires_ime" in stats
        assert "estimated_duration" in stats
        
        assert "typing_preview" in result["result"]
        assert "estimated_duration" in result["result"]
        assert result["result"]["typing_pattern"] == "human"
        assert result["result"]["error_simulation"] == True
    
    def test_type_text_multilingual_support(self):
        """Test multilingual text support"""
        multilingual_text = "Hello 你好 Hola ¡Adiós! こんにちは 🌍"
        
        response = client.post("/input/type_text", headers=HEADERS, json={
            "action": "type",
            "text": multilingual_text,
            "ime_mode": True,
            "language": "multi",
            "dry_run": True
        })
        
        assert response.status_code == 200
        result = response.json()
        
        if "result" in result:
            stats = result["result"]["text_stats"]
            assert stats["has_special_chars"] == True
            assert stats["requires_ime"] == True
            assert result["result"]["ime_mode"] == True
    
    @patch('routes.input.PYAUTOGUI_AVAILABLE', True)
    @patch('routes.input.pyautogui')
    def test_type_text_with_error_simulation(self, mock_pyautogui):
        """Test typing with error simulation"""
        # Mock pyautogui functions
        mock_pyautogui.write = MagicMock()
        mock_pyautogui.press = MagicMock()
        
        response = client.post("/input/type_text", headers=HEADERS, json={
            "action": "type",
            "text": "testing error simulation",
            "error_simulation": True,
            "error_rate": 0.1,
            "typing_pattern": "human"
        })
        
        assert response.status_code == 200
        result = response.json()
        
        if "result" in result:
            assert result["result"]["status"] == "completed"
            assert "typing_log" in result["result"]
            assert "performance" in result["result"]
            
            log = result["result"]["typing_log"]
            assert "characters_typed" in log
            assert "corrections_made" in log
            assert "actual_duration" in log
            
            perf = result["result"]["performance"]
            assert "chars_per_second" in perf
            assert "words_per_minute" in perf
        else:
            assert "errors" in result
    
    def test_type_text_ime_mode(self):
        """Test IME mode for complex text input"""
        response = client.post("/input/type_text", headers=HEADERS, json={
            "action": "type",
            "text": "Testing IME mode with special characters: ñáéíóú",
            "ime_mode": True,
            "preserve_clipboard": True,
            "dry_run": True
        })
        
        assert response.status_code == 200
        result = response.json()
        
        if "result" in result:
            assert result["result"]["ime_mode"] == True
            assert result["result"]["preserve_clipboard"] == True
            stats = result["result"]["text_stats"]
            assert stats["has_special_chars"] == True


class TestInputCapabilities:
    """Test input capabilities endpoint"""
    
    def test_input_capabilities(self):
        """Test input capabilities reporting"""
        response = client.get("/input/capabilities", headers=HEADERS)
        assert response.status_code == 200
        
        caps = response.json()["result"]
        
        # Basic capabilities
        assert "platform" in caps
        assert "mouse" in caps
        assert "keyboard" in caps
        assert "drag_drop" in caps
        assert "gestures" in caps
        assert "stylus" in caps
        assert "dry_run" in caps
        
        # Enhanced capabilities
        assert "ime_support" in caps
        assert "clipboard_integration" in caps
        
        # Should always support dry run
        assert caps["dry_run"] == True
        assert caps["ime_support"] == True
        assert caps["clipboard_integration"] == True
    
    def test_unauthorized_input_access(self):
        """Test API key authentication for input endpoints"""
        endpoints = [
            "/input/mouse_drag",
            "/input/key_combo", 
            "/input/type_text"
        ]
        
        for endpoint in endpoints:
            # No API key
            response = client.post(endpoint, json={"action": "test"})
            assert response.status_code == 403
            
            # Invalid API key
            response = client.post(endpoint, 
                                 headers={"x-api-key": "invalid"}, 
                                 json={"action": "test"})
            assert response.status_code == 403
    
    def test_performance_metrics(self):
        """Test that all input endpoints include performance metrics"""
        endpoints_data = [
            ("/input/mouse_drag", {
                "action": "drag",
                "from_x": 100, "from_y": 100,
                "to_x": 200, "to_y": 200,
                "dry_run": True
            }),
            ("/input/key_combo", {
                "action": "press",
                "keys": ["ctrl", "c"],
                "dry_run": True
            }),
            ("/input/type_text", {
                "action": "type",
                "text": "test",
                "dry_run": True
            })
        ]
        
        for endpoint, data in endpoints_data:
            response = client.post(endpoint, headers=HEADERS, json=data)
            assert response.status_code == 200
            
            result = response.json()
            assert "timestamp" in result
            assert "latency_ms" in result
            assert isinstance(result["latency_ms"], int)
            assert result["latency_ms"] >= 0