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


# Do not import pyautogui at the module level to avoid DISPLAY errors in headless environments
PYAUTOGUI_AVAILABLE = None
def _import_pyautogui():
    global PYAUTOGUI_AVAILABLE
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        PYAUTOGUI_AVAILABLE = True
        return pyautogui
    except (ImportError, KeyError) as e:
        # KeyError can occur if DISPLAY is not set
        PYAUTOGUI_AVAILABLE = False
        return None

# Platform-specific accessibility imports
if platform.system() == "Linux":
    try:
        from Xlib import display, X  # type: ignore
        from Xlib.ext import randr  # type: ignore
        XLIB_AVAILABLE = True
    except ImportError:
        XLIB_AVAILABLE = False
elif platform.system() == "Windows":
    try:
        import win32gui  # type: ignore
        import win32con  # type: ignore
        import win32api  # type: ignore
        WIN32_AVAILABLE = True
    except ImportError:
        WIN32_AVAILABLE = False
elif platform.system() == "Darwin":
    try:
        import Quartz  # type: ignore
        import ApplicationServices  # type: ignore
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

def _error_response(code: str, message: str, extra: Optional[Dict] = None, start_time: Optional[float] = None) -> Dict:
    """Create standardized error response"""
    current_time = time.time()
    result = {
        "errors": [{"code": code, "message": message}],
        "timestamp": int(current_time * 1000)
    }
    if start_time is not None:
        result["latency_ms"] = int((current_time - start_time) * 1000)
    if extra:
        result.update(extra)
    return result

def _get_monitors():
    """Get comprehensive information about available monitors with enhanced detection"""
    monitors = []
    
    if platform.system() == "Linux" and XLIB_AVAILABLE:
        try:
            d = display.Display()
            screen = d.screen()
            resources = randr.get_screen_resources(screen.root)
            
            for i, output in enumerate(resources.outputs):
                output_info = randr.get_output_info(d, output, resources.config_timestamp)
                if output_info.connection == randr.Connected and output_info.crtc:
                    crtc = randr.get_crtc_info(d, output_info.crtc, resources.config_timestamp)
                    # Get DPI information if available
                    dpi_x = dpi_y = 96  # Default DPI
                    try:
                        if output_info.mm_width > 0 and output_info.mm_height > 0:
                            dpi_x = int(crtc.width * 25.4 / output_info.mm_width)
                            dpi_y = int(crtc.height * 25.4 / output_info.mm_height)
                    except:
                        pass
                    
                    monitors.append({
                        "index": i,
                        "x": crtc.x,
                        "y": crtc.y, 
                        "width": crtc.width,
                        "height": crtc.height,
                        "primary": i == 0,
                        "scale_factor": max(dpi_x, dpi_y) / 96.0,
                        "dpi": {"x": dpi_x, "y": dpi_y},
                        "name": f"Monitor_{i}",
                        "rotation": 0  # Could detect rotation if needed
                    })
        except Exception as e:
            # Enhanced fallback with system detection
            try:
                # Try to get screen dimensions from environment
                display_env = os.environ.get("DISPLAY")
                if display_env:
                    # Parse display info if available
                    screen_width = int(os.environ.get("SCREEN_WIDTH", "1920"))
                    screen_height = int(os.environ.get("SCREEN_HEIGHT", "1080"))
                else:
                    screen_width, screen_height = 1920, 1080
            except:
                screen_width, screen_height = 1920, 1080
                
            monitors.append({
                "index": 0, "x": 0, "y": 0, 
                "width": screen_width, "height": screen_height, 
                "primary": True, "scale_factor": 1.0,
                "dpi": {"x": 96, "y": 96}, "name": "Primary", "rotation": 0
            })
    
    elif platform.system() == "Windows" and WIN32_AVAILABLE:
        try:
            # Enhanced Windows monitor detection
            import win32api
            import win32con
            
            def enum_display_monitor(hMonitor, hdcMonitor, lprcMonitor, dwData):
                monitors.append({
                    "index": len(monitors),
                    "x": lprcMonitor[0],
                    "y": lprcMonitor[1],
                    "width": lprcMonitor[2] - lprcMonitor[0],
                    "height": lprcMonitor[3] - lprcMonitor[1],
                    "primary": len(monitors) == 0,
                    "scale_factor": 1.0,  # Could get actual DPI scaling
                    "dpi": {"x": 96, "y": 96},
                    "name": f"Monitor_{len(monitors)}",
                    "rotation": 0
                })
                return True
            
            win32api.EnumDisplayMonitors(None, None, enum_display_monitor, 0)
            
        except Exception:
            # Windows fallback
            try:
                width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
                height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
                monitors.append({
                    "index": 0, "x": 0, "y": 0,
                    "width": width, "height": height,
                    "primary": True, "scale_factor": 1.0,
                    "dpi": {"x": 96, "y": 96}, "name": "Primary", "rotation": 0
                })
            except:
                monitors.append({
                    "index": 0, "x": 0, "y": 0, "width": 1920, "height": 1080,
                    "primary": True, "scale_factor": 1.0,
                    "dpi": {"x": 96, "y": 96}, "name": "Primary", "rotation": 0
                })
    
    elif platform.system() == "Darwin" and QUARTZ_AVAILABLE:
        try:
            # Enhanced macOS monitor detection
            display_count = Quartz.CGGetActiveDisplayList(10, None, None)[1]
            for i in range(display_count):
                display_id = Quartz.CGGetActiveDisplayList(10, None, None)[2][i]
                bounds = Quartz.CGDisplayBounds(display_id)
                
                monitors.append({
                    "index": i,
                    "x": int(bounds.origin.x),
                    "y": int(bounds.origin.y),
                    "width": int(bounds.size.width),
                    "height": int(bounds.size.height),
                    "primary": Quartz.CGDisplayIsMain(display_id),
                    "scale_factor": 1.0,  # Could get Retina scaling
                    "dpi": {"x": 72, "y": 72},  # macOS default
                    "name": f"Display_{i}",
                    "rotation": 0
                })
        except Exception:
            monitors.append({
                "index": 0, "x": 0, "y": 0, "width": 1920, "height": 1080,
                "primary": True, "scale_factor": 1.0,
                "dpi": {"x": 72, "y": 72}, "name": "Primary", "rotation": 0
            })
    
    elif PYAUTOGUI_AVAILABLE:
        try:
            # Enhanced PyAutoGUI detection with multiple monitors
            size = pyautogui.size()
            monitors.append({
                "index": 0,
                "x": 0,
                "y": 0,
                "width": size.width,
                "height": size.height,
                "primary": True,
                "scale_factor": 1.0,
                "dpi": {"x": 96, "y": 96},
                "name": "Primary",
                "rotation": 0
            })
        except Exception:
            monitors.append({
                "index": 0, "x": 0, "y": 0, "width": 1920, "height": 1080,
                "primary": True, "scale_factor": 1.0,
                "dpi": {"x": 96, "y": 96}, "name": "Primary", "rotation": 0
            })
    
    else:
        # Default fallback with enhanced metadata
        monitors.append({
            "index": 0, "x": 0, "y": 0, "width": 1920, "height": 1080,
            "primary": True, "scale_factor": 1.0,
            "dpi": {"x": 96, "y": 96}, "name": "Primary", "rotation": 0
        })
    
    return monitors

def _capture_screenshot(region=None, monitor=0, scale_factor=1.0):
    """Enhanced screenshot capture with validation and error handling"""
    if not PYAUTOGUI_AVAILABLE:
        raise Exception("PyAutoGUI not available for screenshot capture")
    
    pyautogui = _import_pyautogui()
    if not pyautogui:
        raise Exception("PyAutoGUI not available or DISPLAY not set for screenshot capture")
    
    try:
        monitors = _get_monitors()
        
        # Validate monitor index
        if monitor >= len(monitors):
            raise Exception(f"Invalid monitor index {monitor}. Available monitors: 0-{len(monitors)-1}")
        
        selected_monitor = monitors[monitor]
        
        if region:
            # Validate region bounds
            if region["x"] < 0 or region["y"] < 0:
                raise Exception("Region coordinates cannot be negative")
            if region["width"] <= 0 or region["height"] <= 0:
                raise Exception("Region dimensions must be positive")
                
            # Adjust region for monitor offset
            adjusted_region = (
                selected_monitor["x"] + region["x"],
                selected_monitor["y"] + region["y"],
                region["width"],
                region["height"]
            )
            
            # Validate region doesn't exceed monitor bounds
            max_x = selected_monitor["x"] + selected_monitor["width"]
            max_y = selected_monitor["y"] + selected_monitor["height"]
            
            if (adjusted_region[0] + adjusted_region[2]) > max_x:
                raise Exception(f"Region extends beyond monitor width ({max_x} pixels)")
            if (adjusted_region[1] + adjusted_region[3]) > max_y:
                raise Exception(f"Region extends beyond monitor height ({max_y} pixels)")
            
            screenshot = pyautogui.screenshot(region=adjusted_region)
        else:
            # Full screen capture
            if len(monitors) == 1:
                screenshot = pyautogui.screenshot()
            else:
                # For multi-monitor, capture the specific monitor
                monitor_region = (
                    selected_monitor["x"],
                    selected_monitor["y"], 
                    selected_monitor["width"],
                    selected_monitor["height"]
                )
                screenshot = pyautogui.screenshot(region=monitor_region)
        
        # Apply DPI scaling if needed
        if scale_factor != 1.0 and scale_factor > 0:
            new_width = int(screenshot.width * scale_factor)
            new_height = int(screenshot.height * scale_factor)
            if PIL_AVAILABLE:
                screenshot = screenshot.resize((new_width, new_height), Image.LANCZOS)
            else:
                # Basic resize without PIL
                screenshot = screenshot.resize((new_width, new_height))
        
        return screenshot, selected_monitor
        
    except Exception as e:
        raise Exception(f"Screenshot capture failed: {str(e)}")

@router.post("/capture", dependencies=[Depends(verify_key)])
def screen_capture(req: ScreenCaptureRequest, response: Response):
    """
    Enhanced screenshot capture with multi-monitor and HiDPI support.
    Supports full screen, regional, and multi-monitor capture with comprehensive validation.
    """
    pyautogui = _import_pyautogui()
    if not pyautogui:
        return _error_response("MISSING_DEPENDENCY", "PyAutoGUI is not available or DISPLAY is not set on this system.")
    start_time = time.time()
    
    if req.action != "capture":
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}", start_time=start_time)
    
    if not PYAUTOGUI_AVAILABLE:
        return _error_response("DEPENDENCY_MISSING", "PyAutoGUI not available for screen capture", start_time=start_time)
    
    # Input validation
    if req.monitor < 0:
        return _error_response("INVALID_MONITOR", "Monitor index cannot be negative", start_time=start_time)
    
    if req.scale <= 0:
        return _error_response("INVALID_SCALE", "Scale factor must be positive", start_time=start_time)
    
    if req.quality < 1 or req.quality > 100:
        return _error_response("INVALID_QUALITY", "JPEG quality must be between 1-100", start_time=start_time)
    
    if req.format not in ["png", "jpeg", "base64"]:
        return _error_response("INVALID_FORMAT", "Format must be 'png', 'jpeg', or 'base64'", start_time=start_time)
    
    try:
        monitors = _get_monitors()
        
        # Validate monitor index
        if req.monitor >= len(monitors):
            return _error_response("INVALID_MONITOR", f"Monitor {req.monitor} not available. Found {len(monitors)} monitors.", start_time=start_time)
        
        # Enhanced capture with validation
        screenshot, selected_monitor = _capture_screenshot(req.region, req.monitor, req.scale)
        
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
                    "monitor": {
                        "index": req.monitor,
                        "name": selected_monitor["name"],
                        "dimensions": {
                            "x": selected_monitor["x"],
                            "y": selected_monitor["y"],
                            "width": selected_monitor["width"],
                            "height": selected_monitor["height"]
                        },
                        "dpi": selected_monitor["dpi"],
                        "scale_factor": selected_monitor["scale_factor"],
                        "primary": selected_monitor["primary"]
                    },
                    "region": req.region,
                    "applied_scale": req.scale,
                    "capture_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                },
                "monitors": monitors,
                "timestamp": int(time.time() * 1000),
                "latency_ms": int((time.time() - start_time) * 1000)
            }
        else:
            # Enhanced file output with metadata
            timestamp = int(time.time())
            temp_path = f"/tmp/screenshot_{timestamp}_m{req.monitor}.{req.format}"
            
            if req.format == "jpeg":
                screenshot.save(temp_path, format="JPEG", quality=req.quality, optimize=True)
            else:
                screenshot.save(temp_path, format="PNG", optimize=True)
                
            # Create metadata file alongside the image
            metadata_path = temp_path.replace(f".{req.format}", "_metadata.json")
            metadata = {
                "capture_timestamp": timestamp,
                "monitor": selected_monitor,
                "region": req.region,
                "applied_scale": req.scale,
                "format": req.format,
                "file_path": temp_path,
                "dimensions": {"width": screenshot.width, "height": screenshot.height}
            }
            
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
                
            return {
                "result": {
                    "file_path": temp_path,
                    "metadata_path": metadata_path,
                    "format": req.format,
                    "width": screenshot.width,
                    "height": screenshot.height,
                    "monitor": {
                        "index": req.monitor,
                        "name": selected_monitor["name"],
                        "dimensions": {
                            "x": selected_monitor["x"],
                            "y": selected_monitor["y"],
                            "width": selected_monitor["width"],
                            "height": selected_monitor["height"]
                        },
                        "dpi": selected_monitor["dpi"],
                        "scale_factor": selected_monitor["scale_factor"],
                        "primary": selected_monitor["primary"]
                    },
                    "region": req.region,
                    "applied_scale": req.scale,
                    "file_size_bytes": os.path.getsize(temp_path) if os.path.exists(temp_path) else 0
                },
                "monitors": monitors,
                "timestamp": int(time.time() * 1000),
                "latency_ms": int((time.time() - start_time) * 1000)
            }
            
    except Exception as e:
        return _error_response("CAPTURE_ERROR", str(e), start_time=start_time)

@router.post("/ocr", dependencies=[Depends(verify_key)])
def ocr_read_region(req: OCRRequest, response: Response):
    """
    Enhanced OCR text extraction from screen regions or images.
    Supports multiple languages, confidence scoring, and detailed word-level analysis.
    """
    start_time = time.time()
    
    if req.action != "read":
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    if not TESSERACT_AVAILABLE:
        return _error_response("DEPENDENCY_MISSING", "pytesseract not available for OCR")
    
    # Input validation
    if req.confidence_threshold < 0 or req.confidence_threshold > 100:
        return _error_response("INVALID_CONFIDENCE", "Confidence threshold must be between 0-100")
    
    if req.language and not all(c.isalnum() or c in ['_', '+'] for c in req.language):
        return _error_response("INVALID_LANGUAGE", "Language code contains invalid characters")
    
    try:
        # Get image to process
        image_source = "screen_capture"
        if req.image_data:
            # Decode base64 image
            try:
                image_bytes = base64.b64decode(req.image_data)
                import io
                image = Image.open(io.BytesIO(image_bytes))
                image_source = "base64_data"
            except Exception as e:
                return _error_response("INVALID_IMAGE_DATA", f"Failed to decode image data: {str(e)}")
        else:
            # Capture screen region
            if not PYAUTOGUI_AVAILABLE:
                return _error_response("DEPENDENCY_MISSING", "PyAutoGUI required for screen capture")
            
            try:
                screenshot, monitor_info = _capture_screenshot(req.region, 0)  # Default to monitor 0
                image = screenshot
            except Exception as e:
                return _error_response("CAPTURE_ERROR", f"Failed to capture screen: {str(e)}")
        
        # Prepare OCR configuration
        config_parts = [
            '--oem 3',  # OCR Engine Mode: Default
            '--psm 6',  # Page Segmentation Mode: Uniform block of text
            f'-l {req.language}'  # Language
        ]
        
        # Add additional OCR optimizations
        config_parts.extend([
            '-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,-:;!?()[]{}',
            '-c preserve_interword_spaces=1'
        ])
        
        custom_config = ' '.join(config_parts)
        
        # Enhanced OCR processing with multiple output formats
        try:
            # Get detailed word-level data
            ocr_data = pytesseract.image_to_data(image, config=custom_config, output_type=pytesseract.Output.DICT)
            
            # Get full text with confidence
            full_text = pytesseract.image_to_string(image, config=custom_config)
            
            # Get bounding boxes
            boxes = pytesseract.image_to_boxes(image, config=custom_config)
            
        except Exception as e:
            return _error_response("OCR_PROCESSING_ERROR", f"OCR processing failed: {str(e)}")
        
        # Process and filter results by confidence threshold
        filtered_words = []
        lines = []
        current_line = []
        current_line_num = -1
        
        for i in range(len(ocr_data['text'])):
            confidence = int(ocr_data['conf'][i])
            text = ocr_data['text'][i].strip()
            
            if confidence >= req.confidence_threshold and text:
                word_data = {
                    "text": text,
                    "confidence": confidence,
                    "bbox": {
                        "x": ocr_data['left'][i],
                        "y": ocr_data['top'][i],
                        "width": ocr_data['width'][i],
                        "height": ocr_data['height'][i]
                    },
                    "block_num": ocr_data['block_num'][i],
                    "par_num": ocr_data['par_num'][i],
                    "line_num": ocr_data['line_num'][i],
                    "word_num": ocr_data['word_num'][i]
                }
                
                filtered_words.append(word_data)
                
                # Group words by lines
                line_num = ocr_data['line_num'][i]
                if line_num != current_line_num:
                    if current_line:
                        lines.append({
                            "line_num": current_line_num,
                            "text": " ".join([w["text"] for w in current_line]),
                            "words": current_line,
                            "avg_confidence": sum([w["confidence"] for w in current_line]) / len(current_line),
                            "bbox": _calculate_line_bbox(current_line)
                        })
                    current_line = [word_data]
                    current_line_num = line_num
                else:
                    current_line.append(word_data)
        
        # Add the last line
        if current_line:
            lines.append({
                "line_num": current_line_num,
                "text": " ".join([w["text"] for w in current_line]),
                "words": current_line,
                "avg_confidence": sum([w["confidence"] for w in current_line]) / len(current_line),
                "bbox": _calculate_line_bbox(current_line)
            })
        
        # Calculate overall statistics
        if filtered_words:
            avg_confidence = sum([w["confidence"] for w in filtered_words]) / len(filtered_words)
            min_confidence = min([w["confidence"] for w in filtered_words])
            max_confidence = max([w["confidence"] for w in filtered_words])
        else:
            avg_confidence = min_confidence = max_confidence = 0
        
        return {
            "result": {
                "text": full_text.strip(),
                "words": filtered_words,
                "lines": lines,
                "language": req.language,
                "region": req.region,
                "image_source": image_source,
                "statistics": {
                    "total_words": len(filtered_words),
                    "total_lines": len(lines),
                    "confidence_threshold": req.confidence_threshold,
                    "avg_confidence": round(avg_confidence, 2),
                    "min_confidence": min_confidence,
                    "max_confidence": max_confidence,
                    "words_filtered": len([w for w in ocr_data['text'] if w.strip()]) - len(filtered_words)
                },
                "config_used": custom_config,
                "image_dimensions": {"width": image.width, "height": image.height} if hasattr(image, 'width') else None
            },
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return _error_response("OCR_ERROR", str(e))

def _calculate_line_bbox(words):
    """Calculate bounding box for a line of words"""
    if not words:
        return {"x": 0, "y": 0, "width": 0, "height": 0}
    
    min_x = min([w["bbox"]["x"] for w in words])
    min_y = min([w["bbox"]["y"] for w in words])
    max_x = max([w["bbox"]["x"] + w["bbox"]["width"] for w in words])
    max_y = max([w["bbox"]["y"] + w["bbox"]["height"] for w in words])
    
    return {
        "x": min_x,
        "y": min_y,
        "width": max_x - min_x,
        "height": max_y - min_y
    }

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