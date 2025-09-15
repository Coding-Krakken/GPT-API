
from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel
import subprocess, os, platform, time, threading, psutil
from utils.platform_tools import is_windows
from utils.auth import verify_key
from utils.gui_env import detect_gui_environment, ensure_x11_or_fail, get_install_guidance, log_full_gui_env
import random

# In-memory registry for launched app instances (PID -> metadata)
_apps_registry = {}
_apps_registry_lock = threading.Lock()
_env_cache = {"gui_env": None, "full_env": None, "ts": 0}
_ENV_CACHE_TTL = 5  # seconds
def _generate_pid():
    # Use a random int for demo; in real use, use actual process PID
    return random.randint(10000, 99999)

def _now_ts():
    return int(time.time() * 1000)

def _get_cached_env():
    now = time.time()
    if _env_cache["gui_env"] is not None and now - _env_cache["ts"] < _ENV_CACHE_TTL:
        return _env_cache["gui_env"], _env_cache["full_env"]
    gui_env = detect_gui_environment() or {}
    full_env = log_full_gui_env() or {}
    _env_cache["gui_env"] = gui_env
    _env_cache["full_env"] = full_env
    _env_cache["ts"] = now
    return gui_env, full_env

router = APIRouter()

@router.get("/capabilities", dependencies=[Depends(verify_key)])
def get_app_capabilities():
    """
    Returns a dictionary of supported /apps features for the current OS/session.
    """
    import shutil
    import sys
    os_type = platform.system()
    capabilities = {
        "os": os_type,
        "gui": False,
        "process_management": True,
        "window_management": False,
        "multi_window": False,
        "geometry": False,
        "state": False,
        "wayland": False,
        "x11": False,
        "tools": {},
    }
    if os_type == "Linux":
        display = os.environ.get("DISPLAY")
        wayland = os.environ.get("WAYLAND_DISPLAY")
        capabilities["wayland"] = bool(wayland)
        capabilities["x11"] = bool(display)
        if display and shutil.which("wmctrl"):
            capabilities["gui"] = True
            capabilities["window_management"] = True
            capabilities["multi_window"] = True
            capabilities["geometry"] = True
            capabilities["state"] = True
            capabilities["tools"]["wmctrl"] = True
            capabilities["tools"]["xprop"] = bool(shutil.which("xprop"))
        if wayland:
            # TODO: Detect swaymsg or other tools for Wayland
            capabilities["tools"]["swaymsg"] = bool(shutil.which("swaymsg"))
    elif os_type == "Darwin":
        capabilities["gui"] = True
        capabilities["window_management"] = True
        capabilities["multi_window"] = False  # AppleScript is limited
        capabilities["geometry"] = False
        capabilities["state"] = False
        capabilities["tools"]["osascript"] = bool(shutil.which("osascript"))
    elif os_type == "Windows":
        capabilities["gui"] = True
        capabilities["window_management"] = True
        capabilities["multi_window"] = False  # PowerShell/pywin32 is limited
        capabilities["geometry"] = False
        capabilities["state"] = False
        capabilities["tools"]["powershell"] = bool(shutil.which("powershell"))
        try:
            import win32gui
            capabilities["tools"]["pywin32"] = True
        except ImportError:
            capabilities["tools"]["pywin32"] = False
    capabilities["python_version"] = platform.python_version()
    return capabilities

# /apps endpoint: Cross-platform process and GUI window management.
# Linux: X11 (wmctrl), Wayland (not yet supported), headless (error).
# macOS: AppleScript/osascript.
# Windows: PowerShell/pywin32.

from typing import Optional

class AppRequest(BaseModel):
    action: Optional[str] = None
    app: Optional[str] = None
    args: str = ""
    filter: Optional[str] = None  # For filtering app list
    limit: Optional[int] = 100    # For paging app list
    offset: Optional[int] = 0     # For paging app list
    # GUI interaction fields
    window_title: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    pid: Optional[int] = None  # For direct PID matching
    window_index: Optional[int] = 0  # For multi-window selection (default: first match)
    # Window management fields
    workspace: Optional[int] = None  # Virtual desktop/workspace number
    snap_position: Optional[str] = None  # "left", "right", "top", "bottom", "maximize", "minimize"
    tile_position: Optional[str] = None  # "top-left", "top-right", "bottom-left", "bottom-right"
    pin_to_top: Optional[bool] = None  # Always on top
    # Special action for window enumeration
    # action: 'list_windows' returns all open windows (Linux/X11 only for now)

@router.post("/", dependencies=[Depends(verify_key)])
def handle_app_action(req: AppRequest, response: Response):
    gui_env, full_env = _get_cached_env()
    expected_keys = [
        "DISPLAY", "WAYLAND_DISPLAY", "XDG_SESSION_TYPE", "os", "x11", "wayland", "wmctrl", "xprop", "swaymsg", "xvfb", "vnc", "vnc_display", "missing_tools", "test_mode", "display", "wayland_display", "session_type"
    ]
    for k in expected_keys:
        if k not in gui_env:
            gui_env[k] = None
        if k not in full_env:
            full_env[k] = None
    if not isinstance(gui_env["missing_tools"], list):
        gui_env["missing_tools"] = []
    if not isinstance(full_env["missing_tools"], list):
        full_env["missing_tools"] = []
    # Always set test_mode correctly
    if os.environ.get("GUI_TEST_MODE") == "1":
        full_env["test_mode"] = True
    elif full_env["test_mode"] is None:
        full_env["test_mode"] = False



    import re
    start_time = time.time()
    def error_response(code, message, status_code=400, extra=None, errors=None):
        response.status_code = 200  # Always return 200, put status in response body
        err_obj = {"code": code, "message": message}
        if extra:
            err_obj.update(extra)
        err = {
            "errors": [err_obj],
            "timestamp": _now_ts(),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        return err

    # Input sanitization helpers
    SAFE_APP_RE = re.compile(r'^[\w\-\.]+$')
    DANGEROUS_ARG_PATTERNS = [r'[`$\\]|;|\|', r'\brm\b', r'\bshutdown\b', r'\breboot\b', r'\bmkfs\b', r'\bdd\b', r'\b:(){:|:&};:\b']
    def is_safe_app(app):
        return bool(app and SAFE_APP_RE.match(app))
    def is_safe_args(args):
        if not args:
            return True
        for pat in DANGEROUS_ARG_PATTERNS:
            if re.search(pat, args, re.IGNORECASE):
                return False
        return True

    # Headless GUI awareness
    is_headless = not gui_env.get("gui")

    # Schema enforcement and validation per action
    action = req.action
    if not action:
        return error_response("MISSING_ACTION", "'action' field is required.")

    if action == "list" or action == "list_windows":
        # List apps or windows
        if is_windows():
            try:
                from utils.win32_windows import list_windows
                winlist = list_windows()
                windows = []
                for w in winlist:
                    windows.append({
                        "window_id": w["hwnd"],
                        "pid": w["pid"],
                        "title": w["title"]
                    })
                return {"result": {"windows": windows}, "env": full_env, "timestamp": _now_ts(), "latency_ms": int((time.time() - start_time) * 1000)}
            except Exception as e:
                return error_response("WINDOW_LIST_ERROR", f"Failed to list windows: {str(e)}", 500, {"env": full_env})
        elif action == "list_windows":
            required_tools = ["wmctrl", "xprop"]
            path_dirs = os.environ.get("PATH")
            if not path_dirs:
                missing = required_tools.copy()
            else:
                path_dirs = path_dirs.split(":")
                missing = []
                for tool in required_tools:
                    found = False
                    for d in path_dirs:
                        if d and os.path.exists(os.path.join(d, tool)):
                            found = True
                            break
                    if not found:
                        missing.append(tool)
            if missing:
                if os.environ.get("GUI_TEST_MODE") == "1":
                    full_env["test_mode"] = True
                elif full_env["test_mode"] is None:
                    full_env["test_mode"] = False
                return error_response("MISSING_TOOLS", get_install_guidance(missing), 500, {"missing_tools": missing, "env": full_env})
            # Actually list windows using wmctrl
            try:
                import subprocess
                result = subprocess.run(["wmctrl", "-lG"], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    windows = []
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            parts = line.split()
                            if len(parts) >= 8:
                                win_id = parts[0]
                                desktop = parts[1]
                                pid = parts[2] if parts[2] != '-1' else None
                                geometry = {
                                    "x": int(parts[3]),
                                    "y": int(parts[4]),
                                    "width": int(parts[5]),
                                    "height": int(parts[6])
                                }
                                title = ' '.join(parts[7:])
                                windows.append({
                                    "window_id": win_id,
                                    "desktop": desktop,
                                    "pid": pid,
                                    "title": title,
                                    "geometry": geometry
                                })
                    return {"result": {"windows": windows}, "env": full_env, "timestamp": _now_ts(), "latency_ms": int((time.time() - start_time) * 1000)}
                else:
                    return {"result": {"windows": []}, "env": full_env, "timestamp": _now_ts(), "latency_ms": int((time.time() - start_time) * 1000)}
            except Exception as e:
                return error_response("WINDOW_LIST_ERROR", f"Failed to list windows: {str(e)}", 500, {"env": full_env})
        # For app list (not windows), return all active instances
        with _apps_registry_lock:
            apps = []
            for pid, meta in _apps_registry.items():
                # Simulate resource usage if psutil is available and pid is real
                cpu = mem = uptime = None
                try:
                    # If you use real subprocesses, replace with actual PID
                    # For demo, just randomize
                    cpu = round(random.uniform(0, 5), 2)
                    mem = round(random.uniform(10, 100), 2)
                    uptime = int((_now_ts() - meta["launched_at"]) / 1000)
                except Exception:
                    pass
                # Geometry/state: if GUI, simulate geometry; else None
                geometry = meta.get("geometry")
                if gui_env.get("gui") and geometry is None:
                    geometry = {"x": random.randint(0, 1000), "y": random.randint(0, 1000), "width": 800, "height": 600}
                state = meta.get("state", "running")
                apps.append({
                    "pid": pid,
                    "app": meta["app"],
                    "args": meta["args"],
                    "state": state,
                    "geometry": geometry,
                    "launched_at": meta["launched_at"],
                    "cpu_percent": cpu,
                    "mem_mb": mem,
                    "uptime_sec": uptime
                })
        return {"result": {"apps": apps}, "env": full_env, "timestamp": _now_ts(), "latency_ms": int((time.time() - start_time) * 1000)}

    if action == "launch":
        if req.app is None or req.app == "":
            return error_response("MISSING_FIELD", "'app' is required for launch.")
        if not is_safe_app(req.app):
            return error_response("INVALID_APP", "'app' contains invalid characters.")
        if not is_safe_args(req.args):
            return error_response("DANGEROUS_ARGS", "Arguments contain potentially dangerous patterns.", 403)
        # Simulate launching a process and assign a unique PID
        with _apps_registry_lock:
            pid = _generate_pid()
            while pid in _apps_registry:
                pid = _generate_pid()
            meta = {
                "app": req.app,
                "args": req.args,
                "state": "running",
                "geometry": None,
                "launched_at": _now_ts(),
            }
            _apps_registry[pid] = meta
        return {"result": {"status": "ok", "action": action, "app": req.app, "pid": pid}, "env": full_env, "timestamp": _now_ts(), "latency_ms": int((time.time() - start_time) * 1000)}

    if action == "kill":
        if req.pid is None:
            return error_response("MISSING_FIELD", "'pid' required for kill.")
        with _apps_registry_lock:
            meta = _apps_registry.get(req.pid)
            if not meta:
                return error_response("NOT_FOUND", f"No such PID: {req.pid}")
            meta["state"] = "terminated"
            # Optionally, remove from registry: del _apps_registry[req.pid]
        return {"result": {"status": "ok", "action": action, "pid": req.pid}, "env": full_env, "timestamp": _now_ts(), "latency_ms": int((time.time() - start_time) * 1000)}

    if action in ("resize", "move", "snap", "tile", "pin", "virtual_desktop"):
        if is_headless:
            return error_response("HEADLESS_ENVIRONMENT", "GUI operations not allowed in headless mode.", 403)
        if req.pid is None:
            return error_response("MISSING_FIELD", "'pid' required for window operations.")
        
        with _apps_registry_lock:
            meta = _apps_registry.get(req.pid)
            if not meta:
                return error_response("NOT_FOUND", f"No such PID: {req.pid}")
            
            # Handle different window operations
            if action in ("resize", "move"):
                if req.x is None or req.y is None or req.width is None or req.height is None:
                    return error_response("MISSING_FIELD", "'x', 'y', 'width', and 'height' required for geometry ops.")
                if not (0 <= req.x <= 10000 and 0 <= req.y <= 10000 and 1 <= req.width <= 10000 and 1 <= req.height <= 10000):
                    return error_response("INVALID_GEOMETRY", "Geometry values out of bounds.")
                meta["geometry"] = {"x": req.x, "y": req.y, "width": req.width, "height": req.height}
                return {"result": {"status": "ok", "action": action, "pid": req.pid, "geometry": meta["geometry"]}, "env": full_env, "timestamp": _now_ts(), "latency_ms": int((time.time() - start_time) * 1000)}
            
            elif action == "snap":
                if not req.snap_position:
                    return error_response("MISSING_FIELD", "'snap_position' required for snap operation.")
                valid_positions = ["left", "right", "top", "bottom", "maximize", "minimize"]
                if req.snap_position not in valid_positions:
                    return error_response("INVALID_SNAP_POSITION", f"snap_position must be one of: {valid_positions}")
                
                # Simulate snapping
                snap_geometries = {
                    "left": {"x": 0, "y": 0, "width": 960, "height": 1080},
                    "right": {"x": 960, "y": 0, "width": 960, "height": 1080},
                    "top": {"x": 0, "y": 0, "width": 1920, "height": 540},
                    "bottom": {"x": 0, "y": 540, "width": 1920, "height": 540},
                    "maximize": {"x": 0, "y": 0, "width": 1920, "height": 1080},
                    "minimize": {"x": 0, "y": 0, "width": 0, "height": 0}
                }
                meta["geometry"] = snap_geometries[req.snap_position]
                meta["snap_position"] = req.snap_position
                return {"result": {"status": "ok", "action": action, "pid": req.pid, "snap_position": req.snap_position, "geometry": meta["geometry"]}, "env": full_env, "timestamp": _now_ts(), "latency_ms": int((time.time() - start_time) * 1000)}
            
            elif action == "tile":
                if not req.tile_position:
                    return error_response("MISSING_FIELD", "'tile_position' required for tile operation.")
                valid_positions = ["top-left", "top-right", "bottom-left", "bottom-right"]
                if req.tile_position not in valid_positions:
                    return error_response("INVALID_TILE_POSITION", f"tile_position must be one of: {valid_positions}")
                
                # Simulate tiling
                tile_geometries = {
                    "top-left": {"x": 0, "y": 0, "width": 960, "height": 540},
                    "top-right": {"x": 960, "y": 0, "width": 960, "height": 540},
                    "bottom-left": {"x": 0, "y": 540, "width": 960, "height": 540},
                    "bottom-right": {"x": 960, "y": 540, "width": 960, "height": 540}
                }
                meta["geometry"] = tile_geometries[req.tile_position]
                meta["tile_position"] = req.tile_position
                return {"result": {"status": "ok", "action": action, "pid": req.pid, "tile_position": req.tile_position, "geometry": meta["geometry"]}, "env": full_env, "timestamp": _now_ts(), "latency_ms": int((time.time() - start_time) * 1000)}
            
            elif action == "pin":
                pin_state = req.pin_to_top if req.pin_to_top is not None else True
                meta["pin_to_top"] = pin_state
                return {"result": {"status": "ok", "action": action, "pid": req.pid, "pin_to_top": pin_state}, "env": full_env, "timestamp": _now_ts(), "latency_ms": int((time.time() - start_time) * 1000)}
            
            elif action == "virtual_desktop":
                if req.workspace is None:
                    return error_response("MISSING_FIELD", "'workspace' required for virtual desktop operation.")
                if not (0 <= req.workspace <= 10):
                    return error_response("INVALID_WORKSPACE", "workspace must be between 0 and 10.")
                meta["workspace"] = req.workspace
                return {"result": {"status": "ok", "action": action, "pid": req.pid, "workspace": req.workspace}, "env": full_env, "timestamp": _now_ts(), "latency_ms": int((time.time() - start_time) * 1000)}

    # Unknown or unsupported action
    return error_response("UNSUPPORTED_ACTION", f"Action '{action}' is not supported.", 400)
