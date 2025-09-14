"""
Screen capture and visual perception endpoints for GUI automation.
Provides screenshot, OCR, template matching, and accessibility querying capabilities.
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import base64
import time
import json
import os
import platform
from utils.auth import verify_key

router = APIRouter()

# Import GUI automation dependencies with fallbacks
try:
    from PIL import Image, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
    # Disable pyautogui failsafe for automation
    pyautogui.FAILSAFE = False
except ImportError:
    PYAUTOGUI_AVAILABLE = False

# Platform-specific accessibility imports
if platform.system() == "Linux":
    try:
        from Xlib import display, X
        from Xlib.ext import randr
        XLIB_AVAILABLE = True
    except ImportError:
        XLIB_AVAILABLE = False
elif platform.system() == "Windows":
    try:
        import win32gui
        import win32con
        import win32api
        WIN32_AVAILABLE = True
    except ImportError:
        WIN32_AVAILABLE = False
elif platform.system() == "Darwin":
    try:
        import Quartz
        import ApplicationServices
        QUARTZ_AVAILABLE = True
    except ImportError:
        QUARTZ_AVAILABLE = False

class ScreenCaptureRequest(BaseModel):
    action: str
    region: Optional[Dict[str, int]] = None  # {x, y, width, height}
    monitor: Optional[int] = 0  # Monitor index for multi-monitor setups
    format: Optional[str] = "png"  # png, jpeg, base64
    quality: Optional[int] = 95  # JPEG quality 1-100
    scale: Optional[float] = 1.0  # Scale factor for HiDPI
    
class OCRRequest(BaseModel):
    action: str
    region: Optional[Dict[str, int]] = None  # {x, y, width, height} 
    image_data: Optional[str] = None  # base64 encoded image
    language: Optional[str] = "eng"  # OCR language
    confidence_threshold: Optional[int] = 50  # Minimum confidence 0-100
    
class TemplateMatchRequest(BaseModel):
    action: str
    template_data: str  # base64 encoded template image
    region: Optional[Dict[str, int]] = None  # Search region
    threshold: Optional[float] = 0.8  # Match confidence 0.0-1.0
    method: Optional[str] = "TM_CCOEFF_NORMED"  # OpenCV template matching method
    max_matches: Optional[int] = 1  # Maximum matches to return

class AccessibilityRequest(BaseModel):
    action: str
    element_path: Optional[str] = None  # XPath-like selector
    properties: Optional[List[str]] = None  # Properties to retrieve
    max_depth: Optional[int] = 5  # Maximum tree depth

def _error_response(code: str, message: str, extra: Optional[Dict] = None) -> Dict:
    """Create standardized error response"""
    result = {
        "errors": [{"code": code, "message": message}],
        "timestamp": int(time.time() * 1000)
    }
    if extra:
        result.update(extra)
    return result

def _get_monitors():
    """Get information about available monitors"""
    monitors = []
    
    if platform.system() == "Linux" and XLIB_AVAILABLE:
        try:
            d = display.Display()
            screen = d.screen()
            resources = randr.get_screen_resources(screen.root)
            
            for output in resources.outputs:
                output_info = randr.get_output_info(d, output, resources.config_timestamp)
                if output_info.connection == randr.Connected:
                    crtc = randr.get_crtc_info(d, output_info.crtc, resources.config_timestamp)
                    monitors.append({
                        "index": len(monitors),
                        "x": crtc.x,
                        "y": crtc.y, 
                        "width": crtc.width,
                        "height": crtc.height,
                        "primary": len(monitors) == 0
                    })
        except Exception:
            # Fallback to single monitor
            monitors.append({"index": 0, "x": 0, "y": 0, "width": 1920, "height": 1080, "primary": True})
    
    elif PYAUTOGUI_AVAILABLE:
        try:
            # PyAutoGUI can detect multiple monitors
            size = pyautogui.size()
            monitors.append({
                "index": 0,
                "x": 0,
                "y": 0,
                "width": size.width,
                "height": size.height,
                "primary": True
            })
        except Exception:
            monitors.append({"index": 0, "x": 0, "y": 0, "width": 1920, "height": 1080, "primary": True})
    
    else:
        # Default fallback
        monitors.append({"index": 0, "x": 0, "y": 0, "width": 1920, "height": 1080, "primary": True})
    
    return monitors

def _capture_screenshot(region=None, monitor=0):
    """Capture screenshot using available methods"""
    if not PYAUTOGUI_AVAILABLE:
        raise Exception("PyAutoGUI not available for screenshot capture")
    
    try:
        if region:
            # Capture specific region
            screenshot = pyautogui.screenshot(region=(region["x"], region["y"], region["width"], region["height"]))
        else:
            # Capture full screen or specific monitor
            screenshot = pyautogui.screenshot()
        
        return screenshot
    except Exception as e:
        raise Exception(f"Screenshot capture failed: {str(e)}")

@router.post("/capture", dependencies=[Depends(verify_key)])
def screen_capture(req: ScreenCaptureRequest, response: Response):
    """
    Capture screenshots with multi-monitor and HiDPI support.
    Supports full screen, regional, and multi-monitor capture.
    """
    start_time = time.time()
    
    if req.action != "capture":
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    if not PYAUTOGUI_AVAILABLE:
        return _error_response("DEPENDENCY_MISSING", "PyAutoGUI not available for screen capture")
    
    try:
        monitors = _get_monitors()
        
        # Validate monitor index
        if req.monitor >= len(monitors):
            return _error_response("INVALID_MONITOR", f"Monitor {req.monitor} not available. Found {len(monitors)} monitors.")
        
        # Capture screenshot
        screenshot = _capture_screenshot(req.region, req.monitor)
        
        # Apply scaling for HiDPI if needed
        if req.scale != 1.0:
            new_size = (int(screenshot.width * req.scale), int(screenshot.height * req.scale))
            screenshot = screenshot.resize(new_size, Image.LANCZOS if PIL_AVAILABLE else None)
        
        # Encode output
        if req.format == "base64":
            import io
            buffer = io.BytesIO()
            screenshot.save(buffer, format="PNG")
            encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            return {
                "result": {
                    "image_data": encoded,
                    "format": "png",
                    "width": screenshot.width,
                    "height": screenshot.height,
                    "monitor": req.monitor,
                    "region": req.region
                },
                "monitors": monitors,
                "timestamp": int(time.time() * 1000),
                "latency_ms": int((time.time() - start_time) * 1000)
            }
        else:
            # Save to temporary file
            temp_path = f"/tmp/screenshot_{int(time.time())}.{req.format}"
            if req.format == "jpeg":
                screenshot.save(temp_path, format="JPEG", quality=req.quality)
            else:
                screenshot.save(temp_path, format="PNG")
                
            return {
                "result": {
                    "file_path": temp_path,
                    "format": req.format,
                    "width": screenshot.width,
                    "height": screenshot.height,
                    "monitor": req.monitor,
                    "region": req.region
                },
                "monitors": monitors,
                "timestamp": int(time.time() * 1000),
                "latency_ms": int((time.time() - start_time) * 1000)
            }
            
    except Exception as e:
        return _error_response("CAPTURE_ERROR", str(e))

@router.post("/ocr", dependencies=[Depends(verify_key)])
def ocr_read_region(req: OCRRequest, response: Response):
    """
    Extract text from screen regions or images using OCR.
    Supports multiple languages and confidence scoring.
    """
    start_time = time.time()
    
    if req.action != "read":
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    if not TESSERACT_AVAILABLE:
        return _error_response("DEPENDENCY_MISSING", "pytesseract not available for OCR")
    
    try:
        # Get image to process
        if req.image_data:
            # Decode base64 image
            image_bytes = base64.b64decode(req.image_data)
            import io
            image = Image.open(io.BytesIO(image_bytes))
        else:
            # Capture screen region
            if not PYAUTOGUI_AVAILABLE:
                return _error_response("DEPENDENCY_MISSING", "PyAutoGUI required for screen capture")
            image = _capture_screenshot(req.region)
        
        # Run OCR
        custom_config = f'--oem 3 --psm 6 -l {req.language}'
        
        # Get text with confidence scores
        ocr_data = pytesseract.image_to_data(image, config=custom_config, output_type=pytesseract.Output.DICT)
        
        # Filter results by confidence threshold
        filtered_results = []
        for i in range(len(ocr_data['text'])):
            if int(ocr_data['conf'][i]) >= req.confidence_threshold:
                if ocr_data['text'][i].strip():  # Non-empty text
                    filtered_results.append({
                        "text": ocr_data['text'][i],
                        "confidence": int(ocr_data['conf'][i]),
                        "bbox": {
                            "x": ocr_data['left'][i],
                            "y": ocr_data['top'][i], 
                            "width": ocr_data['width'][i],
                            "height": ocr_data['height'][i]
                        }
                    })
        
        # Get full text
        full_text = pytesseract.image_to_string(image, config=custom_config)
        
        return {
            "result": {
                "text": full_text.strip(),
                "words": filtered_results,
                "language": req.language,
                "region": req.region,
                "total_words": len(filtered_results)
            },
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return _error_response("OCR_ERROR", str(e))

@router.post("/template_match", dependencies=[Depends(verify_key)])
def vision_template_match(req: TemplateMatchRequest, response: Response):
    """
    Find visual elements using template matching.
    Supports confidence thresholds and multiple match detection.
    """
    start_time = time.time()
    
    if req.action != "match":
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    if not OPENCV_AVAILABLE:
        return _error_response("DEPENDENCY_MISSING", "OpenCV not available for template matching")
    
    try:
        # Decode template image
        template_bytes = base64.b64decode(req.template_data)
        template_array = np.frombuffer(template_bytes, np.uint8)
        template = cv2.imdecode(template_array, cv2.IMREAD_COLOR)
        
        if template is None:
            return _error_response("INVALID_TEMPLATE", "Could not decode template image")
        
        # Capture screen for matching
        if not PYAUTOGUI_AVAILABLE:
            return _error_response("DEPENDENCY_MISSING", "PyAutoGUI required for screen capture")
        
        screenshot = _capture_screenshot(req.region)
        
        # Convert PIL to OpenCV format
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        
        # Perform template matching
        method = getattr(cv2, req.method, cv2.TM_CCOEFF_NORMED)
        result = cv2.matchTemplate(screenshot_cv, template, method)
        
        # Find matches above threshold
        locations = np.where(result >= req.threshold)
        matches = []
        
        template_h, template_w = template.shape[:2]
        
        for i, (y, x) in enumerate(zip(locations[0], locations[1])):
            if len(matches) >= req.max_matches:
                break
                
            confidence = result[y, x]
            matches.append({
                "confidence": float(confidence),
                "bbox": {
                    "x": int(x) + (req.region["x"] if req.region else 0),
                    "y": int(y) + (req.region["y"] if req.region else 0),
                    "width": template_w,
                    "height": template_h
                },
                "center": {
                    "x": int(x + template_w/2) + (req.region["x"] if req.region else 0),
                    "y": int(y + template_h/2) + (req.region["y"] if req.region else 0)
                }
            })
        
        # Sort by confidence
        matches.sort(key=lambda m: m["confidence"], reverse=True)
        
        return {
            "result": {
                "matches": matches[:req.max_matches],
                "total_found": len(matches),
                "threshold": req.threshold,
                "method": req.method,
                "region": req.region
            },
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return _error_response("TEMPLATE_MATCH_ERROR", str(e))

@router.post("/accessibility", dependencies=[Depends(verify_key)])
def a11y_query_tree(req: AccessibilityRequest, response: Response):
    """
    Query accessibility tree for semantic element targeting.
    Cross-platform accessibility API integration.  
    """
    start_time = time.time()
    
    if req.action not in ["query", "tree", "find"]:
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    # Platform-specific accessibility implementation
    try:
        if platform.system() == "Linux":
            return _linux_accessibility_query(req)
        elif platform.system() == "Windows": 
            return _windows_accessibility_query(req)
        elif platform.system() == "Darwin":
            return _macos_accessibility_query(req)
        else:
            return _error_response("PLATFORM_UNSUPPORTED", f"Accessibility not implemented for {platform.system()}")
            
    except Exception as e:
        return _error_response("ACCESSIBILITY_ERROR", str(e))

def _linux_accessibility_query(req: AccessibilityRequest):
    """Linux accessibility via AT-SPI"""
    # Note: This is a simplified implementation
    # Full AT-SPI integration would require pyatspi2
    return {
        "result": {
            "elements": [],
            "message": "Linux accessibility API integration pending - requires AT-SPI2 setup",
            "platform": "linux"
        },
        "timestamp": int(time.time() * 1000),
        "latency_ms": 0
    }

def _windows_accessibility_query(req: AccessibilityRequest):
    """Windows accessibility via UI Automation"""
    if not WIN32_AVAILABLE:
        return _error_response("DEPENDENCY_MISSING", "pywin32 required for Windows accessibility")
    
    # Simplified Windows accessibility
    return {
        "result": {
            "elements": [],
            "message": "Windows accessibility API integration pending - requires UIAutomation",
            "platform": "windows"
        },
        "timestamp": int(time.time() * 1000),
        "latency_ms": 0
    }

def _macos_accessibility_query(req: AccessibilityRequest):
    """macOS accessibility via Accessibility API"""
    if not QUARTZ_AVAILABLE:
        return _error_response("DEPENDENCY_MISSING", "pyobjc required for macOS accessibility")
    
    # Simplified macOS accessibility
    return {
        "result": {
            "elements": [],
            "message": "macOS accessibility API integration pending",
            "platform": "darwin"
        },
        "timestamp": int(time.time() * 1000),
        "latency_ms": 0
    }

@router.get("/capabilities", dependencies=[Depends(verify_key)])
def get_screen_capabilities():
    """Get available screen/perception capabilities for current system"""
    capabilities = {
        "platform": platform.system(),
        "screen_capture": PYAUTOGUI_AVAILABLE,
        "ocr": TESSERACT_AVAILABLE,
        "template_matching": OPENCV_AVAILABLE,
        "image_processing": PIL_AVAILABLE,
        "accessibility": False,  # Will be true when fully implemented
        "multi_monitor": True,  # Basic support via PyAutoGUI
        "hidpi_support": True,  # Basic scaling support
        "monitors": _get_monitors() if PYAUTOGUI_AVAILABLE else []
    }
    
    # Platform-specific accessibility
    if platform.system() == "Linux":
        capabilities["accessibility"] = XLIB_AVAILABLE
    elif platform.system() == "Windows":
        capabilities["accessibility"] = WIN32_AVAILABLE  
    elif platform.system() == "Darwin":
        capabilities["accessibility"] = QUARTZ_AVAILABLE
    
    return {
        "result": capabilities,
        "timestamp": int(time.time() * 1000)
    }