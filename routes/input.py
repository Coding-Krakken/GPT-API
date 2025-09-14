"""
Advanced input synthesis endpoints for GUI automation.
Provides mouse, keyboard, gesture, and stylus input capabilities with safety controls.
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union
import time
import platform
import json
from utils.auth import verify_key
from utils.safety import safety_check, log_action

router = APIRouter()

# Import input automation dependencies with fallbacks
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
    # Configure PyAutoGUI
    pyautogui.FAILSAFE = False  # Disable failsafe for automation
    pyautogui.PAUSE = 0.1  # Default pause between actions
except ImportError:
    PYAUTOGUI_AVAILABLE = False

try:
    from pynput import mouse, keyboard
    from pynput.mouse import Button, Listener as MouseListener
    from pynput.keyboard import Key, Listener as KeyboardListener
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

# Platform-specific input imports
if platform.system() == "Windows":
    try:
        import win32api
        import win32con
        import win32gui
        WIN32_AVAILABLE = True
    except ImportError:
        WIN32_AVAILABLE = False
elif platform.system() == "Darwin":
    try:
        import Quartz
        QUARTZ_AVAILABLE = True
    except ImportError:
        QUARTZ_AVAILABLE = False
elif platform.system() == "Linux":
    try:
        from Xlib import display, X
        from Xlib.ext import record
        from Xlib.protocol import rq
        XLIB_AVAILABLE = True
    except ImportError:
        XLIB_AVAILABLE = False

class MouseDragRequest(BaseModel):
    action: str
    from_x: int
    from_y: int
    to_x: int
    to_y: int
    button: Optional[str] = "left"  # left, right, middle
    duration: Optional[float] = 0.5  # Drag duration in seconds
    steps: Optional[int] = 10  # Number of intermediate steps
    dry_run: Optional[bool] = False
    
class KeyComboRequest(BaseModel):
    action: str
    keys: List[str]  # Key combination like ["ctrl", "c"] or ["alt", "tab"]
    hold_duration: Optional[float] = 0.05  # How long to hold keys
    interval: Optional[float] = 0.01  # Interval between key presses
    dry_run: Optional[bool] = False
    
class TypeTextRequest(BaseModel):
    action: str
    text: str
    typing_speed: Optional[float] = 0.05  # Delay between characters
    preserve_clipboard: Optional[bool] = True
    ime_mode: Optional[bool] = False  # Input Method Editor support
    dry_run: Optional[bool] = False
    
class GestureRequest(BaseModel):
    action: str
    gesture_type: str  # swipe, pinch, rotate, tap, long_press
    points: List[Dict[str, int]]  # List of {x, y} coordinates
    duration: Optional[float] = 1.0
    pressure: Optional[float] = 1.0  # For pressure-sensitive input
    dry_run: Optional[bool] = False
    
class StylusRequest(BaseModel):
    action: str
    points: List[Dict[str, Union[int, float]]]  # {x, y, pressure, tilt_x, tilt_y}
    duration: Optional[float] = 1.0
    brush_size: Optional[int] = 1
    dry_run: Optional[bool] = False

def _error_response(code: str, message: str, extra: Optional[Dict] = None) -> Dict:
    """Create standardized error response"""
    result = {
        "errors": [{"code": code, "message": message}],
        "timestamp": int(time.time() * 1000)
    }
    if extra:
        result.update(extra)
    return result

def _validate_coordinates(x: int, y: int) -> bool:
    """Validate screen coordinates are reasonable"""
    if not PYAUTOGUI_AVAILABLE:
        return True  # Skip validation if PyAutoGUI not available
    
    try:
        screen_width, screen_height = pyautogui.size()
        return 0 <= x <= screen_width and 0 <= y <= screen_height
    except:
        # Fallback validation
        return 0 <= x <= 5000 and 0 <= y <= 5000

def _normalize_button(button: str) -> str:
    """Normalize button names across libraries"""
    button_map = {
        "left": "left",
        "right": "right", 
        "middle": "middle",
        "primary": "left",
        "secondary": "right",
        "auxiliary": "middle"
    }
    return button_map.get(button.lower(), "left")

def _normalize_key(key: str) -> str:
    """Normalize key names across platforms and libraries"""
    key_map = {
        # Modifier keys
        "ctrl": "ctrl",
        "control": "ctrl",
        "cmd": "cmd" if platform.system() == "Darwin" else "ctrl",
        "command": "cmd" if platform.system() == "Darwin" else "ctrl",
        "alt": "alt",
        "option": "alt",
        "shift": "shift",
        "win": "winleft",
        "windows": "winleft",
        "super": "winleft",
        
        # Function keys
        **{f"f{i}": f"f{i}" for i in range(1, 25)},
        
        # Special keys
        "enter": "enter",
        "return": "enter",
        "space": "space",
        "tab": "tab",
        "escape": "esc",
        "esc": "esc",
        "backspace": "backspace",
        "delete": "delete",
        "home": "home",
        "end": "end",
        "pageup": "pageup",
        "pagedown": "pagedown",
        "up": "up",
        "down": "down",
        "left": "left",
        "right": "right",
        "insert": "insert",
        "pause": "pause",
        "capslock": "capslock",
        "numlock": "numlock",
        "scrolllock": "scrolllock",
        "printscreen": "printscreen",
    }
    
    normalized = key_map.get(key.lower(), key.lower())
    return normalized

@router.post("/mouse_drag", dependencies=[Depends(verify_key)])
def mouse_drag(req: MouseDragRequest, response: Response):
    """
    Perform drag and drop operations with precise control.
    Supports smooth dragging with configurable steps and duration.
    """
    start_time = time.time()
    
    if req.action != "drag":
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    # Safety check
    safety_result = safety_check("/input", req.action, req.dict(), req.dry_run)
    if not safety_result["safe"]:
        return _error_response("SAFETY_VIOLATION", safety_result["message"], {"safety": safety_result})
    
    # Validate coordinates
    if not _validate_coordinates(req.from_x, req.from_y):
        return _error_response("INVALID_COORDINATES", f"Invalid start coordinates: ({req.from_x}, {req.from_y})")
    
    if not _validate_coordinates(req.to_x, req.to_y):
        return _error_response("INVALID_COORDINATES", f"Invalid end coordinates: ({req.to_x}, {req.to_y})")
    
    button = _normalize_button(req.button)
    
    result = {
        "action": "drag",
        "from": {"x": req.from_x, "y": req.from_y},
        "to": {"x": req.to_x, "y": req.to_y},
        "button": button,
        "duration": req.duration,
        "steps": req.steps,
        "dry_run": req.dry_run,
        "safety_check": safety_result
    }
    
    if req.dry_run:
        result["status"] = "would_execute"
        log_action("/input", req.action, req.dict(), result, dry_run=True)
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
    
    if not PYAUTOGUI_AVAILABLE:
        return _error_response("DEPENDENCY_MISSING", "PyAutoGUI not available for mouse operations")
    
    try:
        # Move to start position
        pyautogui.moveTo(req.from_x, req.from_y)
        
        # Perform drag operation
        pyautogui.drag(
            req.to_x - req.from_x,  # x offset
            req.to_y - req.from_y,  # y offset
            duration=req.duration,
            button=button
        )
        
        result["status"] = "completed"
        log_action("/input", req.action, req.dict(), result, dry_run=False)
        
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        error_result = _error_response("DRAG_ERROR", str(e))
        log_action("/input", req.action, req.dict(), error_result, dry_run=False)
        return error_result

@router.post("/key_combo", dependencies=[Depends(verify_key)])
def key_combo(req: KeyComboRequest, response: Response):
    """
    Execute keyboard combinations and shortcuts.
    Supports complex key combinations with proper timing.
    """
    start_time = time.time()
    
    if req.action != "press":
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    if not req.keys or len(req.keys) == 0:
        return _error_response("MISSING_KEYS", "No keys specified for combination")
    
    # Normalize key names
    normalized_keys = [_normalize_key(key) for key in req.keys]
    
    if req.dry_run:
        return {
            "result": {
                "action": "key_combo",
                "keys": normalized_keys,
                "original_keys": req.keys,
                "hold_duration": req.hold_duration,
                "interval": req.interval,
                "dry_run": True,
                "status": "would_execute"
            },
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
    
    if not PYAUTOGUI_AVAILABLE:
        return _error_response("DEPENDENCY_MISSING", "PyAutoGUI not available for keyboard operations")
    
    try:
        # Execute key combination
        if len(normalized_keys) == 1:
            # Single key press
            pyautogui.press(normalized_keys[0])
        else:
            # Key combination - use hotkey for simultaneous press
            pyautogui.hotkey(*normalized_keys, interval=req.interval)
        
        return {
            "result": {
                "action": "key_combo", 
                "keys": normalized_keys,
                "original_keys": req.keys,
                "hold_duration": req.hold_duration,
                "interval": req.interval,
                "status": "completed"
            },
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return _error_response("KEY_COMBO_ERROR", str(e))

@router.post("/type_text", dependencies=[Depends(verify_key)])
def type_text(req: TypeTextRequest, response: Response):
    """
    Type text with advanced input method support.
    Handles IME, special characters, and clipboard preservation.
    """
    start_time = time.time()
    
    if req.action != "type":
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    if not req.text:
        return _error_response("MISSING_TEXT", "No text specified for typing")
    
    if req.dry_run:
        return {
            "result": {
                "action": "type_text",
                "text": req.text[:100] + "..." if len(req.text) > 100 else req.text,
                "length": len(req.text),
                "typing_speed": req.typing_speed,
                "ime_mode": req.ime_mode,
                "preserve_clipboard": req.preserve_clipboard,
                "dry_run": True,
                "status": "would_execute"
            },
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
    
    if not PYAUTOGUI_AVAILABLE:
        return _error_response("DEPENDENCY_MISSING", "PyAutoGUI not available for text input")
    
    try:
        # Store original clipboard if requested
        original_clipboard = None
        if req.preserve_clipboard:
            try:
                import pyperclip
                original_clipboard = pyperclip.paste()
            except:
                pass  # Clipboard preservation is optional
        
        # Type text
        if req.ime_mode:
            # For IME support, use clipboard method
            try:
                import pyperclip
                pyperclip.copy(req.text)
                pyautogui.hotkey('ctrl', 'v')
            except:
                # Fallback to direct typing
                pyautogui.write(req.text, interval=req.typing_speed)
        else:
            # Direct typing
            pyautogui.write(req.text, interval=req.typing_speed)
        
        # Restore clipboard if needed
        if req.preserve_clipboard and original_clipboard is not None:
            try:
                import pyperclip
                pyperclip.copy(original_clipboard)
            except:
                pass
        
        return {
            "result": {
                "action": "type_text",
                "length": len(req.text),
                "typing_speed": req.typing_speed,
                "ime_mode": req.ime_mode,
                "preserve_clipboard": req.preserve_clipboard,
                "status": "completed"
            },
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return _error_response("TYPE_TEXT_ERROR", str(e))

@router.post("/gesture", dependencies=[Depends(verify_key)])
def gesture(req: GestureRequest, response: Response):
    """
    Perform touch gestures and multi-point input.
    Supports swipe, pinch, rotate, tap, and long press gestures.
    """
    start_time = time.time()
    
    if req.action != "perform":
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    supported_gestures = ["swipe", "pinch", "rotate", "tap", "long_press", "double_tap"]
    if req.gesture_type not in supported_gestures:
        return _error_response("UNSUPPORTED_GESTURE", f"Gesture '{req.gesture_type}' not supported. Available: {supported_gestures}")
    
    if not req.points or len(req.points) == 0:
        return _error_response("MISSING_POINTS", "No gesture points specified")
    
    # Validate all points
    for i, point in enumerate(req.points):
        if not _validate_coordinates(point["x"], point["y"]):
            return _error_response("INVALID_COORDINATES", f"Invalid coordinates at point {i}: ({point['x']}, {point['y']})")
    
    if req.dry_run:
        return {
            "result": {
                "action": "gesture",
                "gesture_type": req.gesture_type,
                "points": req.points,
                "duration": req.duration,
                "pressure": req.pressure,
                "dry_run": True,
                "status": "would_execute"
            },
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
    
    if not PYAUTOGUI_AVAILABLE:
        return _error_response("DEPENDENCY_MISSING", "PyAutoGUI not available for gesture operations")
    
    try:
        # Execute gesture based on type
        if req.gesture_type == "tap":
            # Simple click at first point
            point = req.points[0]
            pyautogui.click(point["x"], point["y"])
            
        elif req.gesture_type == "double_tap":
            # Double click at first point
            point = req.points[0]
            pyautogui.doubleClick(point["x"], point["y"])
            
        elif req.gesture_type == "long_press":
            # Long press - click and hold
            point = req.points[0]
            pyautogui.mouseDown(point["x"], point["y"])
            time.sleep(req.duration)
            pyautogui.mouseUp()
            
        elif req.gesture_type == "swipe":
            # Swipe between points
            if len(req.points) >= 2:
                start_point = req.points[0]
                end_point = req.points[-1]
                pyautogui.drag(
                    end_point["x"] - start_point["x"],
                    end_point["y"] - start_point["y"],
                    duration=req.duration,
                    button="left"
                )
            
        elif req.gesture_type in ["pinch", "rotate"]:
            # Complex multi-touch gestures - simplified implementation
            # Full implementation would require platform-specific APIs
            return _error_response("GESTURE_LIMITED", f"Gesture '{req.gesture_type}' has limited implementation. Use swipe/tap for now.")
        
        return {
            "result": {
                "action": "gesture",
                "gesture_type": req.gesture_type,
                "points": req.points,
                "duration": req.duration,
                "pressure": req.pressure,
                "status": "completed"
            },
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return _error_response("GESTURE_ERROR", str(e))

@router.post("/stylus", dependencies=[Depends(verify_key)])
def stylus(req: StylusRequest, response: Response):
    """
    Perform stylus/pen input with pressure and tilt sensitivity.
    Supports digital ink, drawing, and annotation workflows.
    """
    start_time = time.time()
    
    if req.action != "draw":
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    if not req.points or len(req.points) == 0:
        return _error_response("MISSING_POINTS", "No stylus points specified")
    
    # Validate all points
    for i, point in enumerate(req.points):
        if not _validate_coordinates(point["x"], point["y"]):
            return _error_response("INVALID_COORDINATES", f"Invalid coordinates at point {i}: ({point['x']}, {point['y']})")
    
    if req.dry_run:
        return {
            "result": {
                "action": "stylus",
                "points": req.points,
                "duration": req.duration,
                "brush_size": req.brush_size,
                "dry_run": True,
                "status": "would_execute"
            },
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
    
    if not PYAUTOGUI_AVAILABLE:
        return _error_response("DEPENDENCY_MISSING", "PyAutoGUI not available for stylus operations")
    
    try:
        # Simplified stylus implementation - draw path between points
        # Full implementation would use platform-specific stylus APIs
        
        if len(req.points) == 1:
            # Single point - tap
            point = req.points[0]
            pyautogui.click(point["x"], point["y"])
        else:
            # Multiple points - draw path
            start_point = req.points[0]
            pyautogui.moveTo(start_point["x"], start_point["y"])
            pyautogui.mouseDown()
            
            # Draw through all points
            total_duration = req.duration / len(req.points) if len(req.points) > 1 else 0.1
            
            for point in req.points[1:]:
                pyautogui.moveTo(point["x"], point["y"], duration=total_duration)
                time.sleep(0.01)  # Small pause for smooth drawing
            
            pyautogui.mouseUp()
        
        return {
            "result": {
                "action": "stylus",
                "points": req.points,
                "duration": req.duration,
                "brush_size": req.brush_size,
                "status": "completed",
                "note": "Simplified stylus implementation - pressure/tilt not fully supported"
            },
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return _error_response("STYLUS_ERROR", str(e))

@router.get("/capabilities", dependencies=[Depends(verify_key)])
def get_input_capabilities():
    """Get available input capabilities for current system"""
    capabilities = {
        "platform": platform.system(),
        "mouse": PYAUTOGUI_AVAILABLE,
        "keyboard": PYAUTOGUI_AVAILABLE,
        "drag_drop": PYAUTOGUI_AVAILABLE,
        "gestures": PYAUTOGUI_AVAILABLE,  # Basic gesture support
        "stylus": PYAUTOGUI_AVAILABLE,    # Basic stylus support
        "ime_support": True,              # Via clipboard method
        "clipboard_integration": True,
        "dry_run": True,                  # Always supported
        "pressure_sensitivity": False,   # Not implemented
        "tilt_sensitivity": False,       # Not implemented
        "multi_touch": False             # Limited implementation
    }
    
    # Enhanced capabilities with additional libraries
    if PYNPUT_AVAILABLE:
        capabilities["advanced_keyboard"] = True
        capabilities["key_monitoring"] = True
        capabilities["mouse_monitoring"] = True
    
    return {
        "result": capabilities,
        "timestamp": int(time.time() * 1000)
    }