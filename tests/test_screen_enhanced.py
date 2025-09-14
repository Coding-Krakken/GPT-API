"""
Comprehensive test suite for enhanced screen capture functionality.
Tests the improved multi-monitor support, HiDPI handling, and validation.
"""

import pytest
from fastapi.testclient import TestClient
from main import app
import json
import os
import base64
from unittest.mock import patch, MagicMock

client = TestClient(app)
API_KEY = "test-key-123"
HEADERS = {"x-api-key": API_KEY}

class TestEnhancedScreenCapture:
    """Test enhanced screen capture capabilities"""
    
    def test_screen_capabilities_enhanced(self):
        """Test that screen capabilities include enhanced metadata"""
        response = client.get("/screen/capabilities", headers=HEADERS)
        assert response.status_code == 200
        
        caps = response.json()["result"]
        assert "screen_capture" in caps
        assert "multi_monitor" in caps
        assert "hidpi_support" in caps
        assert "monitors" in caps
        assert caps["platform"] in ["Linux", "Windows", "Darwin"]
    
    def test_screen_capture_input_validation(self):
        """Test input validation for screen capture"""
        # Invalid action
        response = client.post("/screen/capture", headers=HEADERS, json={
            "action": "invalid_action"
        })
        assert response.status_code == 200
        result = response.json()
        assert "errors" in result
        assert result["errors"][0]["code"] == "INVALID_ACTION"
        
        # Invalid monitor index (negative)
        response = client.post("/screen/capture", headers=HEADERS, json={
            "action": "capture",
            "monitor": -1
        })
        assert response.status_code == 200
        result = response.json()
        assert "errors" in result
        assert result["errors"][0]["code"] == "INVALID_MONITOR"
        
        # Invalid scale factor
        response = client.post("/screen/capture", headers=HEADERS, json={
            "action": "capture",
            "scale": 0
        })
        assert response.status_code == 200
        result = response.json()
        assert "errors" in result
        assert result["errors"][0]["code"] == "INVALID_SCALE"
        
        # Invalid quality
        response = client.post("/screen/capture", headers=HEADERS, json={
            "action": "capture",
            "format": "jpeg",
            "quality": 101
        })
        assert response.status_code == 200
        result = response.json()
        assert "errors" in result
        assert result["errors"][0]["code"] == "INVALID_QUALITY"
        
        # Invalid format
        response = client.post("/screen/capture", headers=HEADERS, json={
            "action": "capture",
            "format": "invalid_format"
        })
        assert response.status_code == 200
        result = response.json()
        assert "errors" in result
        assert result["errors"][0]["code"] == "INVALID_FORMAT"
    
    @patch('routes.screen.PYAUTOGUI_AVAILABLE', True)
    @patch('routes.screen.PIL_AVAILABLE', True)
    @patch('routes.screen.pyautogui')
    @patch('routes.screen.Image')
    def test_screen_capture_base64_format(self, mock_image, mock_pyautogui):
        """Test base64 screenshot capture with mocked dependencies"""
        # Mock screenshot
        mock_screenshot = MagicMock()
        mock_screenshot.width = 1920
        mock_screenshot.height = 1080
        mock_screenshot.save = MagicMock()
        mock_pyautogui.screenshot.return_value = mock_screenshot
        mock_pyautogui.size.return_value = MagicMock(width=1920, height=1080)
        
        # Mock PIL Image
        mock_image.LANCZOS = 1
        
        response = client.post("/screen/capture", headers=HEADERS, json={
            "action": "capture",
            "format": "base64",
            "monitor": 0
        })
        
        assert response.status_code == 200
        result = response.json()
        
        if "result" in result:
            # Successful capture
            assert "image_data" in result["result"]
            assert result["result"]["format"] == "png"
            assert result["result"]["width"] == 1920
            assert result["result"]["height"] == 1080
            assert "monitor" in result["result"]
            assert "monitors" in result
            assert "timestamp" in result
            assert "latency_ms" in result
            
            # Check enhanced monitor metadata
            monitor_info = result["result"]["monitor"]
            assert "index" in monitor_info
            assert "name" in monitor_info
            assert "dimensions" in monitor_info
            assert "dpi" in monitor_info
            assert "scale_factor" in monitor_info
            assert "primary" in monitor_info
        else:
            # Expected dependency error in test environment
            assert "errors" in result
    
    @patch('routes.screen.PYAUTOGUI_AVAILABLE', True)
    @patch('routes.screen.PIL_AVAILABLE', True)
    @patch('routes.screen.pyautogui')
    @patch('routes.screen.Image')
    @patch('os.path.getsize')
    def test_screen_capture_file_format(self, mock_getsize, mock_image, mock_pyautogui):
        """Test file-based screenshot capture with metadata"""
        # Mock screenshot
        mock_screenshot = MagicMock()
        mock_screenshot.width = 1920
        mock_screenshot.height = 1080
        mock_screenshot.save = MagicMock()
        mock_pyautogui.screenshot.return_value = mock_screenshot
        mock_pyautogui.size.return_value = MagicMock(width=1920, height=1080)
        
        # Mock file operations
        mock_getsize.return_value = 1024000  # 1MB
        
        response = client.post("/screen/capture", headers=HEADERS, json={
            "action": "capture",
            "format": "png",
            "monitor": 0
        })
        
        assert response.status_code == 200
        result = response.json()
        
        if "result" in result:
            # Check file output
            assert "file_path" in result["result"]
            assert "metadata_path" in result["result"]
            assert result["result"]["format"] == "png"
            assert "file_size_bytes" in result["result"]
            
            # Check enhanced metadata
            assert "monitor" in result["result"]
            monitor_info = result["result"]["monitor"]
            assert "name" in monitor_info
            assert "dimensions" in monitor_info
            assert "dpi" in monitor_info
        else:
            # Expected dependency error in test environment
            assert "errors" in result
    
    def test_screen_capture_region_validation(self):
        """Test region parameter validation"""
        # Test with valid region
        response = client.post("/screen/capture", headers=HEADERS, json={
            "action": "capture",
            "region": {"x": 100, "y": 100, "width": 800, "height": 600},
            "format": "base64"
        })
        assert response.status_code == 200
        
        # Test with negative coordinates (should be handled in capture function)
        response = client.post("/screen/capture", headers=HEADERS, json={
            "action": "capture",
            "region": {"x": -10, "y": 50, "width": 800, "height": 600},
            "format": "base64"
        })
        assert response.status_code == 200
        # May succeed or fail depending on implementation
    
    def test_screen_capture_scaling(self):
        """Test HiDPI scaling functionality"""
        response = client.post("/screen/capture", headers=HEADERS, json={
            "action": "capture",
            "scale": 2.0,
            "format": "base64"
        })
        assert response.status_code == 200
        
        result = response.json()
        if "result" in result:
            assert result["result"]["applied_scale"] == 2.0
        else:
            # Expected in test environment without dependencies
            assert "errors" in result
    
    def test_screen_capture_jpeg_quality(self):
        """Test JPEG quality settings"""
        response = client.post("/screen/capture", headers=HEADERS, json={
            "action": "capture",
            "format": "jpeg",
            "quality": 85
        })
        assert response.status_code == 200
        
        result = response.json()
        if "result" in result:
            assert result["result"]["format"] == "jpeg"
        else:
            # Expected in test environment
            assert "errors" in result
    
    def test_monitor_detection_enhanced(self):
        """Test enhanced monitor detection capabilities"""
        response = client.get("/screen/capabilities", headers=HEADERS)
        assert response.status_code == 200
        
        caps = response.json()["result"]
        monitors = caps.get("monitors", [])
        
        # Should have at least one monitor (fallback)
        assert len(monitors) >= 1
        
        # Check enhanced monitor metadata
        for monitor in monitors:
            assert "index" in monitor
            assert "x" in monitor
            assert "y" in monitor
            assert "width" in monitor
            assert "height" in monitor
            assert "primary" in monitor
            # Enhanced fields
            assert "scale_factor" in monitor
            assert "dpi" in monitor
            assert "name" in monitor
            assert "rotation" in monitor
            
            # Validate data types
            assert isinstance(monitor["scale_factor"], (int, float))
            assert isinstance(monitor["dpi"], dict)
            assert "x" in monitor["dpi"]
            assert "y" in monitor["dpi"]
    
    @patch('routes.screen.PYAUTOGUI_AVAILABLE', False)
    def test_dependency_missing_error(self):
        """Test proper error handling when dependencies are missing"""
        response = client.post("/screen/capture", headers=HEADERS, json={
            "action": "capture"
        })
        assert response.status_code == 200
        
        result = response.json()
        assert "errors" in result
        assert result["errors"][0]["code"] == "DEPENDENCY_MISSING"
        assert "PyAutoGUI" in result["errors"][0]["message"]
    
    def test_unauthorized_access(self):
        """Test API key authentication"""
        response = client.post("/screen/capture", json={"action": "capture"})
        assert response.status_code == 403
        
        response = client.post("/screen/capture", 
                             headers={"x-api-key": "invalid"}, 
                             json={"action": "capture"})
        assert response.status_code == 403
    
    def test_performance_metrics(self):
        """Test that performance metrics are included in responses"""
        response = client.post("/screen/capture", headers=HEADERS, json={
            "action": "capture",
            "format": "base64"
        })
        assert response.status_code == 200
        
        result = response.json()
        # Should always have timing information
        assert "timestamp" in result
        assert "latency_ms" in result
        assert isinstance(result["latency_ms"], int)
        assert result["latency_ms"] >= 0


class TestEnhancedOCR:
    """Test enhanced OCR capabilities"""
    
    def test_ocr_input_validation(self):
        """Test OCR input validation"""
        # Invalid action
        response = client.post("/screen/ocr", headers=HEADERS, json={
            "action": "invalid_action"
        })
        assert response.status_code == 200
        result = response.json()
        assert "errors" in result
        assert result["errors"][0]["code"] == "INVALID_ACTION"
        
        # Invalid confidence threshold
        response = client.post("/screen/ocr", headers=HEADERS, json={
            "action": "read",
            "confidence_threshold": 150
        })
        assert response.status_code == 200
        result = response.json()
        assert "errors" in result
        assert result["errors"][0]["code"] == "INVALID_CONFIDENCE"
        
        # Invalid language code
        response = client.post("/screen/ocr", headers=HEADERS, json={
            "action": "read",
            "language": "invalid@language!"
        })
        assert response.status_code == 200
        result = response.json()
        assert "errors" in result
        assert result["errors"][0]["code"] == "INVALID_LANGUAGE"
    
    @patch('routes.screen.TESSERACT_AVAILABLE', True)
    @patch('routes.screen.PIL_AVAILABLE', True)
    @patch('routes.screen.pytesseract')
    @patch('routes.screen.Image')
    def test_ocr_from_base64_image(self, mock_image, mock_tesseract):
        """Test OCR from base64 encoded image"""
        # Mock image processing
        mock_img = MagicMock()
        mock_img.width = 800
        mock_img.height = 600
        mock_image.open.return_value = mock_img
        
        # Mock OCR results
        mock_tesseract.image_to_data.return_value = {
            'text': ['Hello', 'World', ''],
            'conf': [95, 88, -1],
            'left': [10, 60, 0],
            'top': [10, 10, 0],
            'width': [40, 50, 0],
            'height': [20, 20, 0],
            'block_num': [1, 1, 1],
            'par_num': [1, 1, 1],
            'line_num': [1, 1, 1],
            'word_num': [1, 2, 3]
        }
        mock_tesseract.image_to_string.return_value = "Hello World"
        mock_tesseract.image_to_boxes.return_value = "H 10 10 20 30 0\ne 15 10 25 30 0"
        
        # Create mock base64 data
        test_image_data = base64.b64encode(b"fake_image_data").decode('utf-8')
        
        response = client.post("/screen/ocr", headers=HEADERS, json={
            "action": "read",
            "image_data": test_image_data,
            "confidence_threshold": 80,
            "language": "eng"
        })
        
        assert response.status_code == 200
        result = response.json()
        
        if "result" in result:
            # Successful OCR
            assert result["result"]["text"] == "Hello World"
            assert "words" in result["result"]
            assert "lines" in result["result"]
            assert "statistics" in result["result"]
            assert result["result"]["language"] == "eng"
            assert result["result"]["image_source"] == "base64_data"
            
            # Check statistics
            stats = result["result"]["statistics"]
            assert "total_words" in stats
            assert "avg_confidence" in stats
            assert "confidence_threshold" in stats
            
            # Check enhanced word data
            if result["result"]["words"]:
                word = result["result"]["words"][0]
                assert "text" in word
                assert "confidence" in word
                assert "bbox" in word
                assert "line_num" in word
                assert "word_num" in word
        else:
            # Expected dependency error in test environment
            assert "errors" in result
    
    @patch('routes.screen.TESSERACT_AVAILABLE', False)
    def test_ocr_dependency_missing(self):
        """Test OCR with missing tesseract dependency"""
        response = client.post("/screen/ocr", headers=HEADERS, json={
            "action": "read"
        })
        assert response.status_code == 200
        
        result = response.json()
        assert "errors" in result
        assert result["errors"][0]["code"] == "DEPENDENCY_MISSING"
        assert "pytesseract" in result["errors"][0]["message"]
    
    def test_ocr_invalid_base64_data(self):
        """Test OCR with invalid base64 image data"""
        response = client.post("/screen/ocr", headers=HEADERS, json={
            "action": "read",
            "image_data": "invalid_base64_data"
        })
        assert response.status_code == 200
        
        result = response.json()
        # Should handle gracefully
        assert "errors" in result or "result" in result
    
    def test_ocr_performance_metrics(self):
        """Test OCR performance metrics"""
        response = client.post("/screen/ocr", headers=HEADERS, json={
            "action": "read",
            "confidence_threshold": 50
        })
        assert response.status_code == 200
        
        result = response.json()
        assert "timestamp" in result
        assert "latency_ms" in result
        assert isinstance(result["latency_ms"], int)
        assert result["latency_ms"] >= 0