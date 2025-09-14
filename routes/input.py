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
    payload_type: Optional[str] = None  # text, file, image, custom
    payload_data: Optional[str] = None  # Data to inject during drag
    interpolation: Optional[str] = "linear"  # linear, ease_in, ease_out, bezier
    click_delay: Optional[float] = 0.1  # Delay before starting drag
    release_delay: Optional[float] = 0.1  # Delay before releasing
    dry_run: Optional[bool] = False
    
class KeyComboRequest(BaseModel):
    action: str
    keys: List[str]  # Key combination like ["ctrl", "c"] or ["alt", "tab"]
    hold_duration: Optional[float] = 0.05  # How long to hold keys
    interval: Optional[float] = 0.01  # Interval between key presses
    sequence_delay: Optional[float] = 0.1  # Delay between key sequences
    repeat_count: Optional[int] = 1  # Number of times to repeat the combination
    press_pattern: Optional[str] = "simultaneous"  # simultaneous, sequential, chord
    release_pattern: Optional[str] = "reverse"  # reverse, simultaneous, sequential
    dry_run: Optional[bool] = False
    
class TypeTextRequest(BaseModel):
    action: str
    text: str
    typing_speed: Optional[float] = 0.05  # Delay between characters
    preserve_clipboard: Optional[bool] = True
    ime_mode: Optional[bool] = False  # Input Method Editor support
    language: Optional[str] = "en"  # Language for IME and validation
    auto_correct: Optional[bool] = False  # Enable auto-correction if available
    typing_pattern: Optional[str] = "uniform"  # uniform, human, burst
    word_delay: Optional[float] = 0.1  # Additional delay between words
    sentence_delay: Optional[float] = 0.2  # Additional delay between sentences
    error_simulation: Optional[bool] = False  # Simulate typing errors
    error_rate: Optional[float] = 0.02  # Error rate for simulation (0-1)
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

def _calculate_drag_path(from_x, from_y, to_x, to_y, steps, interpolation="linear"):
    """Calculate intermediate points for smooth drag operations"""
    if steps <= 1:
        return [(to_x, to_y)]
    
    points = []
    for i in range(1, steps + 1):
        t = i / steps
        
        if interpolation == "ease_in":
            t = t * t
        elif interpolation == "ease_out":
            t = 1 - (1 - t) * (1 - t)
        elif interpolation == "bezier":
            # Simple quadratic bezier with midpoint control
            ctrl_x = (from_x + to_x) / 2
            ctrl_y = from_y - 50  # Pull up slightly for curved path
            t_inv = 1 - t
            x = t_inv * t_inv * from_x + 2 * t_inv * t * ctrl_x + t * t * to_x
            y = t_inv * t_inv * from_y + 2 * t_inv * t * ctrl_y + t * t * to_y
            points.append((int(x), int(y)))
            continue
        
        # Linear interpolation (default)
        x = from_x + (to_x - from_x) * t
        y = from_y + (to_y - from_y) * t
        points.append((int(x), int(y)))
    
    return points

def _inject_drag_payload(payload_type, payload_data):
    """Handle payload injection during drag operations"""
    if not payload_type or not payload_data:
        return {"injected": False}
    
    try:
        if payload_type == "text":
            # Set clipboard content for text payload
            try:
                import pyperclip
                pyperclip.copy(payload_data)
                return {"injected": True, "type": "text", "method": "clipboard"}
            except:
                return {"injected": False, "error": "pyperclip not available"}
        
        elif payload_type == "file":
            # Set file path in clipboard for file operations
            try:
                import pyperclip
                # Create file URI format
                if not payload_data.startswith("file://"):
                    file_uri = f"file://{os.path.abspath(payload_data)}"
                else:
                    file_uri = payload_data
                pyperclip.copy(file_uri)
                return {"injected": True, "type": "file", "method": "clipboard", "uri": file_uri}
            except Exception as e:
                return {"injected": False, "error": str(e)}
        
        elif payload_type == "image":
            # Handle image payload (base64 or file path)
            try:
                if payload_data.startswith("data:image/") or "/" in payload_data:
                    # Image data or file path
                    import pyperclip
                    pyperclip.copy(payload_data)
                    return {"injected": True, "type": "image", "method": "clipboard"}
                else:
                    return {"injected": False, "error": "Invalid image data format"}
            except Exception as e:
                return {"injected": False, "error": str(e)}
        
        elif payload_type == "custom":
            # Custom payload handling
            try:
                import pyperclip
                pyperclip.copy(payload_data)
                return {"injected": True, "type": "custom", "method": "clipboard"}
            except Exception as e:
                return {"injected": False, "error": str(e)}
        
        else:
            return {"injected": False, "error": f"Unsupported payload type: {payload_type}"}
    
    except Exception as e:
        return {"injected": False, "error": f"Payload injection failed: {str(e)}"}

@router.post("/mouse_drag", dependencies=[Depends(verify_key)])
def mouse_drag(req: MouseDragRequest, response: Response):
    """
    Enhanced drag and drop operations with payload injection and smooth interpolation.
    Supports various drag patterns, payload injection, and comprehensive validation.
    """
    start_time = time.time()
    
    if req.action != "drag":
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    # Enhanced input validation
    if req.duration < 0 or req.duration > 30:
        return _error_response("INVALID_DURATION", "Duration must be between 0-30 seconds")
    
    if req.steps < 1 or req.steps > 1000:
        return _error_response("INVALID_STEPS", "Steps must be between 1-1000")
    
    if req.interpolation not in ["linear", "ease_in", "ease_out", "bezier"]:
        return _error_response("INVALID_INTERPOLATION", "Interpolation must be linear, ease_in, ease_out, or bezier")
    
    if req.click_delay < 0 or req.click_delay > 5:
        return _error_response("INVALID_CLICK_DELAY", "Click delay must be between 0-5 seconds")
    
    if req.release_delay < 0 or req.release_delay > 5:
        return _error_response("INVALID_RELEASE_DELAY", "Release delay must be between 0-5 seconds")
    
    if req.payload_type and req.payload_type not in ["text", "file", "image", "custom"]:
        return _error_response("INVALID_PAYLOAD_TYPE", "Payload type must be text, file, image, or custom")
    
    # Safety check with enhanced context
    safety_context = req.dict()
    safety_context["distance"] = ((req.to_x - req.from_x) ** 2 + (req.to_y - req.from_y) ** 2) ** 0.5
    safety_context["has_payload"] = bool(req.payload_type and req.payload_data)
    
    safety_result = safety_check("/input", req.action, safety_context, req.dry_run)
    if not safety_result["safe"]:
        return _error_response("SAFETY_VIOLATION", safety_result["message"], {"safety": safety_result})
    
    # Validate coordinates
    if not _validate_coordinates(req.from_x, req.from_y):
        return _error_response("INVALID_COORDINATES", f"Invalid start coordinates: ({req.from_x}, {req.from_y})")
    
    if not _validate_coordinates(req.to_x, req.to_y):
        return _error_response("INVALID_COORDINATES", f"Invalid end coordinates: ({req.to_x}, {req.to_y})")
    
    # Calculate drag path
    drag_path = _calculate_drag_path(req.from_x, req.from_y, req.to_x, req.to_y, req.steps, req.interpolation)
    
    button = _normalize_button(req.button)
    
    result = {
        "action": "drag",
        "from": {"x": req.from_x, "y": req.from_y},
        "to": {"x": req.to_x, "y": req.to_y},
        "button": button,
        "duration": req.duration,
        "steps": req.steps,
        "interpolation": req.interpolation,
        "path_points": len(drag_path),
        "distance": ((req.to_x - req.from_x) ** 2 + (req.to_y - req.from_y) ** 2) ** 0.5,
        "payload": {
            "type": req.payload_type,
            "has_data": bool(req.payload_data)
        },
        "dry_run": req.dry_run,
        "safety_check": safety_result
    }
    
    if req.dry_run:
        result["status"] = "would_execute"
        result["preview_path"] = drag_path[:5]  # Show first 5 points for preview
        log_action("/input", req.action, req.dict(), result, dry_run=True)
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
    
    if not PYAUTOGUI_AVAILABLE:
        return _error_response("DEPENDENCY_MISSING", "PyAutoGUI not available for mouse operations")
    
    try:
        # Handle payload injection before drag
        payload_result = {"injected": False}
        if req.payload_type and req.payload_data:
            payload_result = _inject_drag_payload(req.payload_type, req.payload_data)
        
        # Move to start position
        pyautogui.moveTo(req.from_x, req.from_y)
        
        # Click delay
        if req.click_delay > 0:
            time.sleep(req.click_delay)
        
        # Start drag
        pyautogui.mouseDown(button=button)
        
        try:
            # Smooth drag along calculated path
            step_duration = req.duration / len(drag_path) if drag_path else 0
            
            for point in drag_path:
                pyautogui.moveTo(point[0], point[1], duration=step_duration)
                time.sleep(0.001)  # Small pause for smoothness
        
        finally:
            # Release delay
            if req.release_delay > 0:
                time.sleep(req.release_delay)
            
            # Always release the mouse button
            pyautogui.mouseUp(button=button)
        
        result["status"] = "completed"
        result["payload_injection"] = payload_result
        result["actual_path_points"] = len(drag_path)
        
        log_action("/input", req.action, req.dict(), result, dry_run=False)
        
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        # Ensure mouse is released on error
        try:
            if PYAUTOGUI_AVAILABLE:
                pyautogui.mouseUp(button=button)
        except:
            pass
        
        error_result = _error_response("DRAG_ERROR", str(e))
        log_action("/input", req.action, req.dict(), error_result, dry_run=False)
        return error_result

@router.post("/key_combo", dependencies=[Depends(verify_key)])
def key_combo(req: KeyComboRequest, response: Response):
    """
    Enhanced keyboard combinations and shortcuts with advanced timing control.
    Supports complex sequences, chords, and precise timing patterns.
    """
    start_time = time.time()
    
    if req.action != "press":
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    if not req.keys or len(req.keys) == 0:
        return _error_response("MISSING_KEYS", "No keys specified for combination")
    
    if len(req.keys) > 10:
        return _error_response("TOO_MANY_KEYS", "Maximum 10 keys allowed in combination")
    
    # Enhanced input validation
    if req.hold_duration < 0 or req.hold_duration > 5:
        return _error_response("INVALID_HOLD_DURATION", "Hold duration must be between 0-5 seconds")
    
    if req.interval < 0 or req.interval > 2:
        return _error_response("INVALID_INTERVAL", "Interval must be between 0-2 seconds")
    
    if req.sequence_delay < 0 or req.sequence_delay > 5:
        return _error_response("INVALID_SEQUENCE_DELAY", "Sequence delay must be between 0-5 seconds")
    
    if req.repeat_count < 1 or req.repeat_count > 100:
        return _error_response("INVALID_REPEAT_COUNT", "Repeat count must be between 1-100")
    
    if req.press_pattern not in ["simultaneous", "sequential", "chord"]:
        return _error_response("INVALID_PRESS_PATTERN", "Press pattern must be simultaneous, sequential, or chord")
    
    if req.release_pattern not in ["reverse", "simultaneous", "sequential"]:
        return _error_response("INVALID_RELEASE_PATTERN", "Release pattern must be reverse, simultaneous, or sequential")
    
    # Normalize key names and validate
    normalized_keys = []
    invalid_keys = []
    
    for key in req.keys:
        normalized = _normalize_key(key)
        if normalized:
            normalized_keys.append(normalized)
        else:
            invalid_keys.append(key)
    
    if invalid_keys:
        return _error_response("INVALID_KEYS", f"Invalid keys: {invalid_keys}")
    
    # Safety check for potentially dangerous combinations
    dangerous_combos = [
        ["ctrl", "alt", "delete"],
        ["cmd", "option", "esc"],
        ["winleft", "l"],
        ["ctrl", "shift", "esc"]
    ]
    
    safety_context = req.dict()
    safety_context["normalized_keys"] = normalized_keys
    safety_context["is_dangerous"] = any(
        set(combo).issubset(set(normalized_keys)) for combo in dangerous_combos
    )
    
    safety_result = safety_check("/input", req.action, safety_context, req.dry_run)
    if not safety_result["safe"]:
        return _error_response("SAFETY_VIOLATION", safety_result["message"], {"safety": safety_result})
    
    result = {
        "action": "key_combo", 
        "keys": normalized_keys,
        "original_keys": req.keys,
        "hold_duration": req.hold_duration,
        "interval": req.interval,
        "sequence_delay": req.sequence_delay,
        "repeat_count": req.repeat_count,
        "press_pattern": req.press_pattern,
        "release_pattern": req.release_pattern,
        "safety_check": safety_result,
        "dry_run": req.dry_run
    }
    
    if req.dry_run:
        result["status"] = "would_execute"
        result["execution_plan"] = _generate_key_execution_plan(normalized_keys, req)
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
    
    if not PYAUTOGUI_AVAILABLE:
        return _error_response("DEPENDENCY_MISSING", "PyAutoGUI not available for keyboard operations")
    
    try:
        execution_log = []
        
        for repeat in range(req.repeat_count):
            if repeat > 0:
                time.sleep(req.sequence_delay)
            
            repeat_log = {"repeat": repeat + 1, "actions": []}
            
            if req.press_pattern == "simultaneous" or len(normalized_keys) == 1:
                # Standard simultaneous key combination
                if len(normalized_keys) == 1:
                    pyautogui.press(normalized_keys[0])
                    repeat_log["actions"].append(f"pressed {normalized_keys[0]}")
                else:
                    pyautogui.hotkey(*normalized_keys, interval=req.interval)
                    repeat_log["actions"].append(f"hotkey {'+'.join(normalized_keys)}")
            
            elif req.press_pattern == "sequential":
                # Sequential key presses with timing
                pressed_keys = []
                try:
                    # Press keys in sequence
                    for key in normalized_keys:
                        pyautogui.keyDown(key)
                        pressed_keys.append(key)
                        repeat_log["actions"].append(f"pressed down {key}")
                        time.sleep(req.interval)
                    
                    # Hold for specified duration
                    time.sleep(req.hold_duration)
                    
                    # Release keys based on pattern
                    if req.release_pattern == "reverse":
                        release_order = list(reversed(pressed_keys))
                    elif req.release_pattern == "sequential":
                        release_order = pressed_keys
                    else:  # simultaneous
                        release_order = pressed_keys
                        req.interval = 0  # No delay for simultaneous release
                    
                    for key in release_order:
                        pyautogui.keyUp(key)
                        repeat_log["actions"].append(f"released {key}")
                        if req.interval > 0:
                            time.sleep(req.interval)
                
                except Exception as e:
                    # Ensure all pressed keys are released
                    for key in pressed_keys:
                        try:
                            pyautogui.keyUp(key)
                        except:
                            pass
                    raise e
            
            elif req.press_pattern == "chord":
                # Chord pattern: press all, hold, release all
                try:
                    # Press all keys
                    for key in normalized_keys:
                        pyautogui.keyDown(key)
                        repeat_log["actions"].append(f"chord press {key}")
                        time.sleep(req.interval)
                    
                    # Hold for duration
                    time.sleep(req.hold_duration)
                    
                    # Release all keys simultaneously
                    for key in normalized_keys:
                        pyautogui.keyUp(key)
                        repeat_log["actions"].append(f"chord release {key}")
                
                except Exception as e:
                    # Cleanup on error
                    for key in normalized_keys:
                        try:
                            pyautogui.keyUp(key)
                        except:
                            pass
                    raise e
            
            execution_log.append(repeat_log)
        
        result["status"] = "completed"
        result["execution_log"] = execution_log
        result["total_actions"] = sum(len(r["actions"]) for r in execution_log)
        
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return _error_response("KEY_COMBO_ERROR", str(e))

def _generate_key_execution_plan(keys, req):
    """Generate execution plan for dry-run preview"""
    plan = []
    
    for repeat in range(req.repeat_count):
        repeat_plan = {"repeat": repeat + 1, "steps": []}
        
        if req.press_pattern == "simultaneous":
            if len(keys) == 1:
                repeat_plan["steps"].append(f"Press {keys[0]}")
            else:
                repeat_plan["steps"].append(f"Hotkey: {'+'.join(keys)}")
        
        elif req.press_pattern == "sequential":
            for key in keys:
                repeat_plan["steps"].append(f"Press down {key}")
                repeat_plan["steps"].append(f"Wait {req.interval}s")
            
            repeat_plan["steps"].append(f"Hold for {req.hold_duration}s")
            
            release_order = list(reversed(keys)) if req.release_pattern == "reverse" else keys
            for key in release_order:
                repeat_plan["steps"].append(f"Release {key}")
                if req.release_pattern != "simultaneous":
                    repeat_plan["steps"].append(f"Wait {req.interval}s")
        
        elif req.press_pattern == "chord":
            repeat_plan["steps"].append(f"Chord press: {', '.join(keys)}")
            repeat_plan["steps"].append(f"Hold for {req.hold_duration}s")
            repeat_plan["steps"].append(f"Chord release: {', '.join(keys)}")
        
        if repeat < req.repeat_count - 1:
            repeat_plan["steps"].append(f"Sequence delay: {req.sequence_delay}s")
        
        plan.append(repeat_plan)
    
    return plan

def _calculate_human_typing_delays(text, base_speed, pattern="uniform"):
    """Calculate human-like typing delays with variations"""
    import random
    import string
    
    delays = []
    
    for i, char in enumerate(text):
        base_delay = base_speed
        
        if pattern == "human":
            # Human-like variations
            if char in string.ascii_uppercase:
                base_delay *= 1.2  # Slightly slower for capitals
            elif char in ".,!?;:":
                base_delay *= 1.5  # Pause at punctuation
            elif char == " ":
                base_delay *= 0.8  # Faster for spaces
            elif char in "aeiou":
                base_delay *= 0.9  # Slightly faster for vowels
            elif char in "qwerty":
                base_delay *= 0.95  # Faster for common keys
            
            # Add random variation (±30%)
            variation = random.uniform(0.7, 1.3)
            base_delay *= variation
        
        elif pattern == "burst":
            # Burst typing pattern - fast segments with pauses
            if i % 10 == 0 and i > 0:
                base_delay *= 3  # Pause every 10 characters
            else:
                base_delay *= 0.6  # Faster typing in bursts
        
        delays.append(max(0.001, base_delay))  # Minimum delay
    
    return delays

def _simulate_typing_errors(text, error_rate=0.02):
    """Simulate realistic typing errors and corrections"""
    import random
    import string
    
    if error_rate <= 0:
        return text, []
    
    chars = list(text)
    corrections = []
    
    # Common typo patterns
    typo_patterns = {
        'a': ['s', 'q'],
        's': ['a', 'd', 'w'],
        'd': ['s', 'f'],
        'f': ['d', 'g'],
        'g': ['f', 'h'],
        'h': ['g', 'j'],
        'j': ['h', 'k'],
        'k': ['j', 'l'],
        'l': ['k', ';'],
        'q': ['w', 'a'],
        'w': ['q', 'e'],
        'e': ['w', 'r'],
        'r': ['e', 't'],
        't': ['r', 'y'],
        'y': ['t', 'u'],
        'u': ['y', 'i'],
        'i': ['u', 'o'],
        'o': ['i', 'p'],
        'p': ['o', '[']
    }
    
    i = 0
    while i < len(chars):
        if random.random() < error_rate and chars[i].lower() in typo_patterns:
            # Insert typo
            original_char = chars[i]
            typo_char = random.choice(typo_patterns[original_char.lower()])
            
            # Insert typo, then correction
            chars[i] = typo_char
            corrections.append({
                "position": i,
                "original": original_char,
                "typo": typo_char,
                "action": "typo_then_correct"
            })
            
            # Insert backspace and correction
            chars.insert(i + 1, '\b')  # Backspace
            chars.insert(i + 2, original_char)  # Correction
            i += 2  # Skip the correction characters
        
        i += 1
    
    return ''.join(chars), corrections

@router.post("/type_text", dependencies=[Depends(verify_key)])
def type_text(req: TypeTextRequest, response: Response):
    """
    Enhanced text input with IME support, multilingual handling, and human-like typing.
    Supports various typing patterns, error simulation, and advanced input methods.
    """
    start_time = time.time()
    
    if req.action != "type":
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    if not req.text:
        return _error_response("MISSING_TEXT", "No text specified for typing")
    
    if len(req.text) > 10000:
        return _error_response("TEXT_TOO_LONG", "Text length exceeds 10,000 characters")
    
    # Enhanced input validation
    if req.typing_speed < 0 or req.typing_speed > 5:
        return _error_response("INVALID_TYPING_SPEED", "Typing speed must be between 0-5 seconds")
    
    if req.word_delay < 0 or req.word_delay > 2:
        return _error_response("INVALID_WORD_DELAY", "Word delay must be between 0-2 seconds")
    
    if req.sentence_delay < 0 or req.sentence_delay > 5:
        return _error_response("INVALID_SENTENCE_DELAY", "Sentence delay must be between 0-5 seconds")
    
    if req.typing_pattern not in ["uniform", "human", "burst"]:
        return _error_response("INVALID_TYPING_PATTERN", "Typing pattern must be uniform, human, or burst")
    
    if req.error_rate < 0 or req.error_rate > 1:
        return _error_response("INVALID_ERROR_RATE", "Error rate must be between 0-1")
    
    if req.language and not req.language.replace("-", "").replace("_", "").isalnum():
        return _error_response("INVALID_LANGUAGE", "Invalid language code format")
    
    # Prepare text with error simulation if enabled
    final_text = req.text
    typing_corrections = []
    
    if req.error_simulation and req.error_rate > 0:
        final_text, typing_corrections = _simulate_typing_errors(req.text, req.error_rate)
    
    # Calculate typing delays
    typing_delays = _calculate_human_typing_delays(final_text, req.typing_speed, req.typing_pattern)
    
    # Analyze text for multilingual support
    text_stats = {
        "character_count": len(req.text),
        "word_count": len(req.text.split()),
        "sentence_count": req.text.count('.') + req.text.count('!') + req.text.count('?'),
        "has_special_chars": any(ord(c) > 127 for c in req.text),
        "requires_ime": req.ime_mode or any(ord(c) > 255 for c in req.text),
        "estimated_duration": sum(typing_delays) + (len(req.text.split()) - 1) * req.word_delay
    }
    
    result = {
        "action": "type_text",
        "text_preview": req.text[:100] + "..." if len(req.text) > 100 else req.text,
        "text_stats": text_stats,
        "typing_speed": req.typing_speed,
        "typing_pattern": req.typing_pattern,
        "ime_mode": req.ime_mode,
        "language": req.language,
        "preserve_clipboard": req.preserve_clipboard,
        "error_simulation": req.error_simulation,
        "corrections_planned": len(typing_corrections),
        "dry_run": req.dry_run
    }
    
    if req.dry_run:
        result["status"] = "would_execute"
        result["estimated_duration"] = text_stats["estimated_duration"]
        result["typing_preview"] = {
            "first_10_delays": typing_delays[:10],
            "corrections": typing_corrections[:3]  # Show first 3 corrections
        }
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
    
    if not PYAUTOGUI_AVAILABLE:
        return _error_response("DEPENDENCY_MISSING", "PyAutoGUI not available for text input")
    
    try:
        # Store original clipboard if requested
        original_clipboard = None
        clipboard_restored = False
        
        if req.preserve_clipboard:
            try:
                import pyperclip
                original_clipboard = pyperclip.paste()
            except:
                pass  # Clipboard preservation is optional
        
        typing_log = {
            "characters_typed": 0,
            "words_typed": 0,
            "corrections_made": 0,
            "ime_switches": 0,
            "actual_duration": 0
        }
        
        typing_start = time.time()
        
        # Handle IME mode or complex characters
        if req.ime_mode or text_stats["requires_ime"]:
            try:
                import pyperclip
                
                # For IME text, use clipboard method for better compatibility
                if text_stats["has_special_chars"]:
                    # Split into chunks for better IME handling
                    chunk_size = 100
                    for i in range(0, len(req.text), chunk_size):
                        chunk = req.text[i:i + chunk_size]
                        pyperclip.copy(chunk)
                        pyautogui.hotkey('ctrl', 'v')
                        typing_log["ime_switches"] += 1
                        time.sleep(0.1)  # Allow IME processing time
                else:
                    # Simple IME mode
                    pyperclip.copy(req.text)
                    pyautogui.hotkey('ctrl', 'v')
                    typing_log["ime_switches"] += 1
                
                typing_log["characters_typed"] = len(req.text)
                typing_log["words_typed"] = len(req.text.split())
            
            except Exception as e:
                # Fallback to direct typing
                for i, char in enumerate(final_text):
                    if char == '\b':
                        pyautogui.press('backspace')
                        typing_log["corrections_made"] += 1
                    else:
                        pyautogui.write(char, interval=0)
                        typing_log["characters_typed"] += 1
                    
                    # Apply calculated delay
                    if i < len(typing_delays):
                        time.sleep(typing_delays[i])
        
        else:
            # Character-by-character typing with timing
            word_chars = 0
            
            for i, char in enumerate(final_text):
                if char == '\b':
                    pyautogui.press('backspace')
                    typing_log["corrections_made"] += 1
                else:
                    pyautogui.write(char, interval=0)
                    typing_log["characters_typed"] += 1
                    
                    # Track words
                    if char == ' ':
                        typing_log["words_typed"] += 1
                        word_chars = 0
                        # Add word delay
                        time.sleep(req.word_delay)
                    elif char in '.!?':
                        # Add sentence delay
                        time.sleep(req.sentence_delay)
                    else:
                        word_chars += 1
                
                # Apply calculated delay
                if i < len(typing_delays):
                    time.sleep(typing_delays[i])
            
            # Count final word if no trailing space
            if word_chars > 0:
                typing_log["words_typed"] += 1
        
        typing_log["actual_duration"] = time.time() - typing_start
        
        # Restore clipboard if needed
        if req.preserve_clipboard and original_clipboard is not None:
            try:
                import pyperclip
                pyperclip.copy(original_clipboard)
                clipboard_restored = True
            except:
                pass
        
        result["status"] = "completed"
        result["typing_log"] = typing_log
        result["clipboard_restored"] = clipboard_restored
        result["performance"] = {
            "chars_per_second": typing_log["characters_typed"] / max(typing_log["actual_duration"], 0.001),
            "words_per_minute": (typing_log["words_typed"] * 60) / max(typing_log["actual_duration"], 0.001)
        }
        
        return {
            "result": result,
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