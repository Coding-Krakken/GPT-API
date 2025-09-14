"""
GUI Control Layer - Full-spectrum GUI automation and introspection
Supports Wayland, X11, headless, and virtual displays with comprehensive observability
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel, Field
import subprocess
import os
import platform
import time
import threading
import json
import psutil
import re
from typing import Optional, List, Dict, Any, Union
from utils.auth import verify_key
from utils.platform_tools import is_windows
from utils.security import safe_subprocess_run, safe_popen
import shutil
from pathlib import Path

# Create routers for organized endpoints
gui_router = APIRouter()
apps_router = APIRouter() 
input_router = APIRouter()
vision_router = APIRouter()

# Global state management
_gui_session_cache = {"data": None, "timestamp": 0}
_gui_cache_ttl = 30  # 30 seconds
_apps_registry = {}
_apps_registry_lock = threading.Lock()

# Structured error codes
GUI_ERRORS = {
    "gui_tool_missing": "Required GUI tool not found",
    "wayland_permission_denied": "Wayland compositor denied access",
    "x11_unreachable": "X11 server unreachable",
    "compositor_blocking": "Compositor blocking requested operation",
    "session_not_detected": "GUI session type not detected",
    "window_not_found": "Target window not found",
    "invalid_geometry": "Invalid window geometry parameters",
    "automation_failed": "GUI automation operation failed"
}

def get_microsecond_timestamp():
    """Get current timestamp with microsecond precision"""
    return int(time.time() * 1000000)

def calculate_latency_us(start_time_us):
    """Calculate latency in microseconds"""
    return get_microsecond_timestamp() - start_time_us

def run_with_observability(command, timeout=10):
    """Run command with full observability and error capture - SECURE VERSION"""
    return safe_subprocess_run(command, timeout=timeout)

def detect_gui_session_comprehensive():
    """Comprehensive GUI session detection for Wayland/X11 hybrid environments"""
    start_time = get_microsecond_timestamp()
    
    session_info = {
        "session_type": None,
        "compositor": None,
        "display": os.environ.get("DISPLAY"),
        "wayland_display": os.environ.get("WAYLAND_DISPLAY"),
        "xdg_session_type": os.environ.get("XDG_SESSION_TYPE"),
        "desktop_session": os.environ.get("XDG_CURRENT_DESKTOP"),
        "tools": {},
        "capabilities": {
            "window_management": False,
            "wayland_introspection": False,
            "x11_fallback": False,
            "screenshot": False,
            "input_automation": False,
            "accessibility": False
        },
        "detection_methods": [],
        "errors": []
    }
    
    # Tool detection
    gui_tools = [
        "wmctrl", "xprop", "xwininfo", "xdotool",  # X11 tools
        "swaymsg", "wlr-randr", "wayland-info",     # Wayland tools
        "xdg-desktop-portal-kde", "xdg-desktop-portal-gnome", "xdg-desktop-portal-wlr",  # Desktop portals
        "Xvfb", "vncserver", "x11vnc",              # Virtual displays
        "scrot", "gnome-screenshot", "spectacle",   # Screenshots
        "xvkbd", "ydotool",                         # Input automation
        "at-spi2-core", "accerciser"                # Accessibility
    ]
    
    for tool in gui_tools:
        session_info["tools"][tool] = bool(shutil.which(tool))
    
    # Determine session type
    if session_info["wayland_display"]:
        session_info["session_type"] = "wayland"
        session_info["detection_methods"].append("WAYLAND_DISPLAY_env")
        
        # Detect Wayland compositor
        if session_info["tools"]["swaymsg"]:
            try:
                result = run_with_observability("swaymsg -t get_version", timeout=5)
                if result["exit_code"] == 0:
                    session_info["compositor"] = "sway"
                    session_info["capabilities"]["window_management"] = True
                    session_info["detection_methods"].append("swaymsg_version")
            except:
                pass
        
        # Check for other Wayland compositors
        for compositor in ["gnome-shell", "kwin_wayland", "weston", "hyprland"]:
            if any(compositor in p.name() for p in psutil.process_iter(['name']) if p.info['name']):
                session_info["compositor"] = compositor
                session_info["detection_methods"].append(f"process_{compositor}")
                break
        
        # Wayland capabilities
        if session_info["tools"]["wlr-randr"]:
            session_info["capabilities"]["wayland_introspection"] = True
        
        # Check for XWayland fallback
        if session_info["display"] and (session_info["tools"]["wmctrl"] or session_info["tools"]["xprop"]):
            session_info["capabilities"]["x11_fallback"] = True
            session_info["detection_methods"].append("xwayland_detected")
            
    elif session_info["display"]:
        session_info["session_type"] = "x11"
        session_info["detection_methods"].append("DISPLAY_env")
        
        # X11 capabilities
        if session_info["tools"]["wmctrl"] and session_info["tools"]["xprop"]:
            session_info["capabilities"]["window_management"] = True
        
        # Detect X11 window manager
        try:
            result = run_with_observability("xprop -root _NET_WM_NAME", timeout=5)
            if result["exit_code"] == 0 and result["stdout"]:
                wm_match = re.search(r'"([^"]+)"', result["stdout"])
                if wm_match:
                    session_info["compositor"] = wm_match.group(1)
                    session_info["detection_methods"].append("xprop_wm_name")
        except:
            pass
    
    # Desktop portal detection for cross-platform screenshot/automation
    portal_tools = ["xdg-desktop-portal-kde", "xdg-desktop-portal-gnome", "xdg-desktop-portal-wlr"]
    if any(session_info["tools"][tool] for tool in portal_tools):
        session_info["capabilities"]["screenshot"] = True
        session_info["capabilities"]["input_automation"] = True
        session_info["detection_methods"].append("desktop_portal")
    
    # Screenshot capabilities
    screenshot_tools = ["scrot", "gnome-screenshot", "spectacle", "xdotool"]
    if any(session_info["tools"][tool] for tool in screenshot_tools):
        session_info["capabilities"]["screenshot"] = True
    
    # Input automation capabilities  
    input_tools = ["xdotool", "ydotool", "xvkbd"]
    if any(session_info["tools"][tool] for tool in input_tools):
        session_info["capabilities"]["input_automation"] = True
        
    # Accessibility capabilities
    if session_info["tools"]["at-spi2-core"]:
        session_info["capabilities"]["accessibility"] = True
    
    # Add timing information
    session_info["detection_latency_us"] = calculate_latency_us(start_time)
    session_info["timestamp"] = start_time
    
    return session_info

def get_cached_gui_session():
    """Get cached GUI session info with TTL"""
    current_time = time.time()
    if (_gui_session_cache["data"] is None or 
        current_time - _gui_session_cache["timestamp"] > _gui_cache_ttl):
        _gui_session_cache["data"] = detect_gui_session_comprehensive()
        _gui_session_cache["timestamp"] = current_time
    return _gui_session_cache["data"]

def list_windows_multi_method():
    """Multi-method window detection with fallbacks"""
    windows = []
    errors = []
    methods_tried = []
    
    session_info = get_cached_gui_session()
    
    # Method 1: wmctrl for X11/XWayland
    if session_info.get("tools", {}).get("wmctrl", False):
        methods_tried.append("wmctrl")
        try:
            result = run_with_observability("wmctrl -lG")
            if result["exit_code"] == 0:
                for line in result["stdout"].split('\n'):
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 8:
                            windows.append({
                                "window_id": parts[0],
                                "desktop": int(parts[1]) if parts[1] != '-1' else None,
                                "pid": int(parts[2]) if parts[2] != '-1' else None,
                                "geometry": {
                                    "x": int(parts[3]),
                                    "y": int(parts[4]), 
                                    "width": int(parts[5]),
                                    "height": int(parts[6])
                                },
                                "title": ' '.join(parts[7:]),
                                "state": "normal",
                                "focus": False,
                                "z_index": None,
                                "method": "wmctrl"
                            })
        except Exception as e:
            errors.append({"method": "wmctrl", "error": str(e)})
    
    # Method 2: swaymsg for Sway/wlroots
    if (session_info.get("tools", {}).get("swaymsg", False) and 
        session_info.get("session_type") == "wayland"):
        methods_tried.append("swaymsg")
        try:
            result = run_with_observability("swaymsg -t get_tree")
            if result["exit_code"] == 0:
                tree_data = json.loads(result["stdout"])
                
                def extract_windows(node, z_index=0):
                    if node.get("type") == "con" and node.get("app_id"):
                        rect = node.get("rect", {})
                        windows.append({
                            "window_id": str(node.get("id")),
                            "desktop": node.get("workspace"),
                            "pid": node.get("pid"),
                            "geometry": {
                                "x": rect.get("x", 0),
                                "y": rect.get("y", 0),
                                "width": rect.get("width", 0),
                                "height": rect.get("height", 0)
                            },
                            "title": node.get("name", ""),
                            "state": "focused" if node.get("focused") else "normal",
                            "focus": node.get("focused", False),
                            "z_index": z_index,
                            "app_id": node.get("app_id"),
                            "method": "swaymsg"
                        })
                    
                    for i, child in enumerate(node.get("nodes", [])):
                        extract_windows(child, z_index + i)
                    for i, child in enumerate(node.get("floating_nodes", [])):
                        extract_windows(child, z_index + 1000 + i)  # Floating windows on top
                
                extract_windows(tree_data)
                
        except Exception as e:
            errors.append({"method": "swaymsg", "error": str(e)})
    
    # Method 3: xdg-desktop-portal via DBus (future implementation)
    if session_info.get("capabilities", {}).get("screenshot", False):
        methods_tried.append("desktop_portal")
        # TODO: Implement DBus introspection
        # This would use python-dbus to query xdg-desktop-portal
    
    # Method 4: /proc filesystem for process-based window linking
    methods_tried.append("proc_environ")
    try:
        for pid in psutil.pids():
            try:
                proc = psutil.Process(pid)
                environ_path = f"/proc/{pid}/environ"
                if os.path.exists(environ_path):
                    with open(environ_path, 'rb') as f:
                        environ_data = f.read().decode('utf-8', errors='ignore')
                        env_vars = dict(item.split('=', 1) for item in environ_data.split('\0') if '=' in item)
                        
                        # Link processes to display servers
                        if ("WAYLAND_DISPLAY" in env_vars or "DISPLAY" in env_vars):
                            # Check if we already have this window from other methods
                            if not any(w.get("pid") == pid for w in windows):
                                windows.append({
                                    "window_id": f"proc_{pid}",
                                    "desktop": None,
                                    "pid": pid,
                                    "geometry": None,  # Unknown via /proc
                                    "title": proc.name(),
                                    "state": proc.status(),
                                    "focus": False,
                                    "z_index": None,
                                    "method": "proc_environ",
                                    "display": env_vars.get("DISPLAY"),
                                    "wayland_display": env_vars.get("WAYLAND_DISPLAY")
                                })
            except (psutil.NoSuchProcess, PermissionError, FileNotFoundError):
                continue
    except Exception as e:
        errors.append({"method": "proc_environ", "error": str(e)})
    
    return {
        "windows": windows,
        "methods_tried": methods_tried,
        "errors": errors,
        "session_info": session_info
    }

# Pydantic models for API endpoints
class GuiSessionResponse(BaseModel):
    session_type: Optional[str] = Field(description="wayland, x11, or None")
    compositor: Optional[str] = Field(description="Name of window manager/compositor")
    display: Optional[str] = Field(description="X11 DISPLAY variable")
    wayland_display: Optional[str] = Field(description="Wayland display socket")
    tools: Dict[str, bool] = Field(description="Available GUI tools")
    capabilities: Dict[str, bool] = Field(description="Available GUI capabilities")
    detection_methods: List[str] = Field(description="Methods used for detection")
    detection_latency_us: int = Field(description="Detection time in microseconds")

class WindowInfo(BaseModel):
    window_id: str
    desktop: Optional[int] = None
    pid: Optional[int] = None
    geometry: Optional[Dict[str, int]] = None
    title: str = ""
    state: str = "normal" 
    focus: bool = False
    z_index: Optional[int] = None
    method: str = "unknown"

class WindowListResponse(BaseModel):
    windows: List[WindowInfo]
    methods_tried: List[str]
    errors: List[Dict[str, str]]
    session_info: Dict[str, Any]

class AppLaunchRequest(BaseModel):
    app: str = Field(description="Application to launch")
    args: str = Field(default="", description="Command line arguments")
    workspace: Optional[int] = Field(default=None, description="Target workspace/desktop")
    geometry: Optional[Dict[str, int]] = Field(default=None, description="Initial window geometry")

class WindowActionRequest(BaseModel):
    action: str = Field(description="Action to perform")
    window_id: Optional[str] = None
    pid: Optional[int] = None
    window_title: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None

class InputRequest(BaseModel):
    action: str = Field(description="input action type")
    text: Optional[str] = None
    key: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None
    button: Optional[str] = Field(default="left", description="Mouse button")
    window_id: Optional[str] = None

class ScreenshotRequest(BaseModel):
    window_id: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    format: str = Field(default="png", description="Image format")

# GUI Session endpoint
@gui_router.get("/session", dependencies=[Depends(verify_key)], response_model=GuiSessionResponse)
def get_gui_session():
    """Get comprehensive GUI session information"""
    session_info = get_cached_gui_session()
    return GuiSessionResponse(**session_info)

@gui_router.get("/test", dependencies=[Depends(verify_key)])
def test_gui_environment():
    """Test GUI detection across different environments"""
    start_time = get_microsecond_timestamp()
    
    # Run comprehensive tests
    tests = {
        "session_detection": False,
        "window_enumeration": False,
        "tool_availability": False,
        "fallback_methods": False
    }
    
    session_info = get_cached_gui_session()
    
    # Test 1: Session detection
    if session_info["session_type"]:
        tests["session_detection"] = True
    
    # Test 2: Window enumeration
    try:
        windows_result = list_windows_multi_method()
        if windows_result["windows"] or windows_result["methods_tried"]:
            tests["window_enumeration"] = True
    except:
        pass
    
    # Test 3: Tool availability
    available_tools = sum(1 for available in session_info["tools"].values() if available)
    if available_tools > 0:
        tests["tool_availability"] = True
    
    # Test 4: Fallback methods
    if session_info["capabilities"]["x11_fallback"] or len(session_info["detection_methods"]) > 1:
        tests["fallback_methods"] = True
    
    return {
        "tests": tests,
        "session_info": session_info,
        "overall_status": "healthy" if all(tests.values()) else "degraded",
        "latency_us": calculate_latency_us(start_time),
        "timestamp": start_time
    }

# Enhanced Apps endpoints with detailed window information
@apps_router.post("/launch", dependencies=[Depends(verify_key)])
def launch_app_with_tracking(request: AppLaunchRequest):
    """Launch app with PID tracking and GUI metadata attachment"""
    start_time = get_microsecond_timestamp()
    
    # Input validation
    if not re.match(r'^[\w\-\.]+$', request.app):
        raise HTTPException(status_code=400, detail={
            "error": {"code": "invalid_app_name", "message": "Invalid application name"}
        })
    
    try:
        # Launch the application
        command = f"{request.app} {request.args}".strip()
        if request.workspace:
            # TODO: Add workspace assignment logic for different compositors
            pass
            
        proc = safe_popen(command)
        
        # Store in registry with metadata
        with _apps_registry_lock:
            app_metadata = {
                "app": request.app,
                "args": request.args,
                "pid": proc.pid,
                "launched_at": start_time,
                "workspace": request.workspace,
                "initial_geometry": request.geometry,
                "status": "running"
            }
            _apps_registry[proc.pid] = app_metadata
        
        return {
            "result": {
                "status": "launched",
                "pid": proc.pid,
                "app": request.app,
                "metadata": app_metadata
            },
            "timestamp": start_time,
            "latency_us": calculate_latency_us(start_time)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "error": {"code": "launch_failed", "message": str(e)},
            "timestamp": start_time,
            "latency_us": calculate_latency_us(start_time)
        })

@apps_router.get("/list_windows_detailed", dependencies=[Depends(verify_key)])
def list_windows_detailed():
    """Get detailed window list with position, size, state, focus, z-index"""
    start_time = get_microsecond_timestamp()
    
    try:
        result = list_windows_multi_method()
        result["timestamp"] = start_time
        result["latency_us"] = calculate_latency_us(start_time)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "error": {"code": "window_enumeration_failed", "message": str(e)},
            "timestamp": start_time,
            "latency_us": calculate_latency_us(start_time)
        })

@apps_router.post("/focus", dependencies=[Depends(verify_key)])
@apps_router.post("/resize", dependencies=[Depends(verify_key)])  
@apps_router.post("/move", dependencies=[Depends(verify_key)])
@apps_router.post("/close", dependencies=[Depends(verify_key)])
def window_control_action(request: WindowActionRequest):
    """Universal window control (focus, resize, move, close)"""
    start_time = get_microsecond_timestamp()
    action = request.action
    
    session_info = get_cached_gui_session()
    
    # Find target window
    target_window = None
    if request.window_id:
        windows_result = list_windows_multi_method()
        target_window = next((w for w in windows_result["windows"] if w["window_id"] == request.window_id), None)
    
    if not target_window and not request.pid:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "window_not_found", "message": "No matching window found"}
        })
    
    try:
        result_data = {"action": action, "success": False}
        
        # X11/XWayland actions using wmctrl
        if session_info["tools"]["wmctrl"] and (session_info["session_type"] == "x11" or session_info["capabilities"]["x11_fallback"]):
            
            if action == "focus":
                if target_window:
                    cmd_result = run_with_observability(f"wmctrl -i -a {target_window['window_id']}")
                    result_data["success"] = cmd_result["exit_code"] == 0
                    result_data["wmctrl_output"] = cmd_result
                    
            elif action == "resize" and all(x is not None for x in [request.x, request.y, request.width, request.height]):
                if target_window:
                    cmd_result = run_with_observability(
                        f"wmctrl -i -r {target_window['window_id']} -e 0,{request.x},{request.y},{request.width},{request.height}"
                    )
                    result_data["success"] = cmd_result["exit_code"] == 0
                    result_data["geometry"] = {"x": request.x, "y": request.y, "width": request.width, "height": request.height}
                    result_data["wmctrl_output"] = cmd_result
                    
            elif action == "move" and request.x is not None and request.y is not None:
                if target_window:
                    # Keep current size, just move
                    geom = target_window.get("geometry", {})
                    width = geom.get("width", 800)
                    height = geom.get("height", 600)
                    cmd_result = run_with_observability(
                        f"wmctrl -i -r {target_window['window_id']} -e 0,{request.x},{request.y},{width},{height}"
                    )
                    result_data["success"] = cmd_result["exit_code"] == 0
                    result_data["geometry"] = {"x": request.x, "y": request.y, "width": width, "height": height}
                    result_data["wmctrl_output"] = cmd_result
                    
            elif action == "close":
                if target_window:
                    cmd_result = run_with_observability(f"wmctrl -i -c {target_window['window_id']}")
                    result_data["success"] = cmd_result["exit_code"] == 0
                    result_data["wmctrl_output"] = cmd_result
        
        # Sway/wlroots actions using swaymsg
        elif session_info["tools"]["swaymsg"] and session_info["session_type"] == "wayland":
            
            if action == "focus" and target_window:
                cmd_result = run_with_observability(f"swaymsg '[con_id=\"{target_window['window_id']}\"] focus'")
                result_data["success"] = cmd_result["exit_code"] == 0
                result_data["swaymsg_output"] = cmd_result
                
            elif action == "resize" and target_window and all(x is not None for x in [request.width, request.height]):
                cmd_result = run_with_observability(
                    f"swaymsg '[con_id=\"{target_window['window_id']}\"] resize set {request.width} {request.height}'"
                )
                result_data["success"] = cmd_result["exit_code"] == 0
                result_data["geometry"] = {"width": request.width, "height": request.height}
                result_data["swaymsg_output"] = cmd_result
                
            elif action == "move" and target_window and request.x is not None and request.y is not None:
                cmd_result = run_with_observability(
                    f"swaymsg '[con_id=\"{target_window['window_id']}\"] move position {request.x} {request.y}'"
                )
                result_data["success"] = cmd_result["exit_code"] == 0
                result_data["geometry"] = {"x": request.x, "y": request.y}
                result_data["swaymsg_output"] = cmd_result
                
            elif action == "close" and target_window:
                cmd_result = run_with_observability(f"swaymsg '[con_id=\"{target_window['window_id']}\"] kill'")
                result_data["success"] = cmd_result["exit_code"] == 0
                result_data["swaymsg_output"] = cmd_result
        
        else:
            result_data["error"] = {"code": "no_suitable_method", "message": "No suitable window management method available"}
        
        return {
            "result": result_data,
            "session_info": session_info,
            "timestamp": start_time,
            "latency_us": calculate_latency_us(start_time)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "error": {"code": "window_action_failed", "message": str(e)},
            "timestamp": start_time,
            "latency_us": calculate_latency_us(start_time)
        })

@apps_router.post("/screenshot", dependencies=[Depends(verify_key)])
def capture_screenshot(request: ScreenshotRequest):
    """Capture window or screen screenshot"""
    start_time = get_microsecond_timestamp()
    
    session_info = get_cached_gui_session() 
    screenshot_path = f"/tmp/screenshot_{int(time.time())}.{request.format}"
    
    try:
        if session_info["tools"]["scrot"]:
            # X11 screenshot with scrot
            if request.window_id:
                cmd_result = run_with_observability(f"scrot -s '{screenshot_path}'")
            else:
                cmd_result = run_with_observability(f"scrot '{screenshot_path}'")
        
        elif session_info["tools"]["gnome-screenshot"]:
            # GNOME screenshot
            if request.window_id:
                cmd_result = run_with_observability(f"gnome-screenshot -w -f '{screenshot_path}'")
            else:
                cmd_result = run_with_observability(f"gnome-screenshot -f '{screenshot_path}'")
        
        else:
            raise HTTPException(status_code=501, detail={
                "error": {"code": "no_screenshot_tool", "message": "No screenshot tool available"}
            })
        
        if cmd_result["exit_code"] == 0 and os.path.exists(screenshot_path):
            # Return screenshot metadata
            file_size = os.path.getsize(screenshot_path)
            return {
                "result": {
                    "screenshot_path": screenshot_path,
                    "format": request.format,
                    "file_size": file_size,
                    "success": True
                },
                "timestamp": start_time,
                "latency_us": calculate_latency_us(start_time)
            }
        else:
            raise HTTPException(status_code=500, detail={
                "error": {"code": "screenshot_failed", "message": "Screenshot capture failed"},
                "cmd_output": cmd_result
            })
            
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "error": {"code": "screenshot_error", "message": str(e)},
            "timestamp": start_time,
            "latency_us": calculate_latency_us(start_time)
        })

# Input automation endpoints
@input_router.post("/keyboard", dependencies=[Depends(verify_key)])
@input_router.post("/mouse", dependencies=[Depends(verify_key)])
@input_router.post("/type", dependencies=[Depends(verify_key)])
def input_automation(request: InputRequest):
    """Input automation: keyboard, mouse, typing"""
    start_time = get_microsecond_timestamp()
    action = request.action
    
    session_info = get_cached_gui_session()
    
    try:
        result_data = {"action": action, "success": False}
        
        # X11 input automation with xdotool
        if session_info["tools"]["xdotool"]:
            
            if action == "type" and request.text:
                cmd_result = run_with_observability(f"xdotool type '{request.text}'")
                result_data["success"] = cmd_result["exit_code"] == 0
                result_data["xdotool_output"] = cmd_result
                
            elif action == "key" and request.key:
                cmd_result = run_with_observability(f"xdotool key {request.key}")
                result_data["success"] = cmd_result["exit_code"] == 0
                result_data["xdotool_output"] = cmd_result
                
            elif action == "click" and request.x is not None and request.y is not None:
                button_map = {"left": "1", "middle": "2", "right": "3"}
                button_num = button_map.get(request.button, "1")
                cmd_result = run_with_observability(f"xdotool mousemove {request.x} {request.y} click {button_num}")
                result_data["success"] = cmd_result["exit_code"] == 0
                result_data["coordinates"] = {"x": request.x, "y": request.y}
                result_data["xdotool_output"] = cmd_result
                
            elif action == "move" and request.x is not None and request.y is not None:
                cmd_result = run_with_observability(f"xdotool mousemove {request.x} {request.y}")
                result_data["success"] = cmd_result["exit_code"] == 0
                result_data["coordinates"] = {"x": request.x, "y": request.y}
                result_data["xdotool_output"] = cmd_result
        
        # Wayland input automation with ydotool
        elif session_info["tools"]["ydotool"]:
            
            if action == "type" and request.text:
                cmd_result = run_with_observability(f"ydotool type '{request.text}'")
                result_data["success"] = cmd_result["exit_code"] == 0
                result_data["ydotool_output"] = cmd_result
                
            elif action == "key" and request.key:
                # ydotool uses different key format, might need mapping
                cmd_result = run_with_observability(f"ydotool key {request.key}")
                result_data["success"] = cmd_result["exit_code"] == 0
                result_data["ydotool_output"] = cmd_result
                
            elif action == "click" and request.x is not None and request.y is not None:
                button_map = {"left": "0xc0", "middle": "0xc1", "right": "0xc2"}
                button_code = button_map.get(request.button, "0xc0")
                cmd_result = run_with_observability(f"ydotool mousemove -a {request.x} {request.y} && ydotool click {button_code}")
                result_data["success"] = cmd_result["exit_code"] == 0
                result_data["coordinates"] = {"x": request.x, "y": request.y}
                result_data["ydotool_output"] = cmd_result
        
        else:
            result_data["error"] = {"code": "no_input_tool", "message": "No suitable input automation tool available"}
        
        return {
            "result": result_data,
            "session_info": session_info,
            "timestamp": start_time,
            "latency_us": calculate_latency_us(start_time)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "error": {"code": "input_automation_failed", "message": str(e)},
            "timestamp": start_time,
            "latency_us": calculate_latency_us(start_time)
        })

# Vision/OCR endpoints (placeholder for future OpenCV/Tesseract integration)
@vision_router.post("/ocr", dependencies=[Depends(verify_key)])
def ocr_text_recognition(screenshot_path: str):
    """OCR text recognition from screenshot"""
    start_time = get_microsecond_timestamp()
    
    # TODO: Implement with pytesseract when available
    return {
        "result": {
            "text": "OCR not yet implemented - requires pytesseract",
            "confidence": 0,
            "words": [],
            "success": False
        },
        "timestamp": start_time,
        "latency_us": calculate_latency_us(start_time)
    }

@vision_router.post("/find_element", dependencies=[Depends(verify_key)])
def visual_element_recognition():
    """Visual element recognition with OpenCV"""
    start_time = get_microsecond_timestamp()
    
    # TODO: Implement with opencv-python when available
    return {
        "result": {
            "elements": [],
            "method": "opencv_template_matching",
            "success": False,
            "message": "Visual recognition not yet implemented - requires opencv-python"
        },
        "timestamp": start_time,
        "latency_us": calculate_latency_us(start_time)
    }

# Mock window for testing
@apps_router.post("/mock_window", dependencies=[Depends(verify_key)])
def create_mock_window():
    """Create a mock window for testing (Xvfb or dummy window)"""
    start_time = get_microsecond_timestamp()
    
    session_info = get_cached_gui_session()
    
    if session_info["tools"]["Xvfb"]:
        # Start Xvfb for testing
        try:
            xvfb_display = ":99"
            cmd_result = run_with_observability(f"Xvfb {xvfb_display} -screen 0 1024x768x24 &")
            
            if cmd_result["exit_code"] == 0:
                # Launch a simple X11 app on the virtual display
                os.environ["DISPLAY"] = xvfb_display
                app_result = run_with_observability("xterm &", timeout=5)
                
                return {
                    "result": {
                        "mock_display": xvfb_display,
                        "xvfb_status": "started",
                        "test_app": "xterm",
                        "success": True
                    },
                    "timestamp": start_time,
                    "latency_us": calculate_latency_us(start_time)
                }
        except Exception as e:
            pass
    
    # Fallback: create a mock registry entry
    mock_pid = 99999
    with _apps_registry_lock:
        _apps_registry[mock_pid] = {
            "app": "mock_window",
            "args": "",
            "pid": mock_pid,
            "launched_at": start_time,
            "geometry": {"x": 100, "y": 100, "width": 400, "height": 300},
            "status": "mock"
        }
    
    return {
        "result": {
            "mock_pid": mock_pid,
            "type": "registry_mock",
            "geometry": {"x": 100, "y": 100, "width": 400, "height": 300},
            "success": True
        },
        "timestamp": start_time,
        "latency_us": calculate_latency_us(start_time)
    }