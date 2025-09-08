
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import subprocess, os, platform
from utils.auth import verify_key

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
    capabilities["python_version"] = sys.version
    return capabilities

# /apps endpoint: Cross-platform process and GUI window management.
# Linux: X11 (wmctrl), Wayland (not yet supported), headless (error).
# macOS: AppleScript/osascript.
# Windows: PowerShell/pywin32.

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import subprocess, os, platform
from utils.auth import verify_key

router = APIRouter()

from typing import Optional

class AppRequest(BaseModel):
    action: str
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
    # Special action for window enumeration
    # action: 'list_windows' returns all open windows (Linux/X11 only for now)

@router.post("/", dependencies=[Depends(verify_key)])
def handle_app_action(req: AppRequest):
    # --- List all open windows (Linux/X11 and Windows) ---
    if req.action == "list_windows":
        os_type = platform.system()
        if os_type == "Linux":
            display = os.environ.get("DISPLAY")
            wayland = os.environ.get("WAYLAND_DISPLAY")
            if not display and not wayland:
                return {"error": "NoGUISession", "detail": "No GUI session detected (neither DISPLAY nor WAYLAND_DISPLAY set). GUI actions require a running desktop session.", "code": 500}, 500
            if wayland and not display:
                # Try Wayland support (Sway/wlroots)
                import shutil
                if shutil.which("swaymsg"):
                    import json
                    def get_sway_windows():
                        result = subprocess.run(["swaymsg", "-t", "get_tree"], capture_output=True, text=True)
                        if result.returncode != 0:
                            return {"error": "SwayMsgError", "detail": f"swaymsg error: {result.stderr}", "code": 500}, 500
                        try:
                            tree = json.loads(result.stdout)
                        except Exception as e:
                            return {"error": "SwayMsgJSONError", "detail": f"swaymsg JSON error: {e}", "code": 500}, 500
                        def collect_windows(node, windows):
                            if node.get("type") == "con" and node.get("window_properties"):
                                windows.append(node)
                            for child in node.get("nodes", []) + node.get("floating_nodes", []):
                                collect_windows(child, windows)
                        windows = []
                        collect_windows(tree, windows)
                        return windows
                    windows = get_sway_windows()
                    if isinstance(windows, tuple):
                        return windows
                    formatted = []
                    for win in windows:
                        formatted.append({
                            "window_id": win.get("id"),
                            "app_id": win.get("app_id"),
                            "pid": win.get("pid"),
                            "title": win.get("name"),
                            "rect": win.get("rect"),
                            "window_properties": win.get("window_properties"),
                        })
                    return {"windows": formatted, "count": len(formatted), "env": {"WAYLAND_DISPLAY": wayland, "XDG_SESSION_TYPE": os.environ.get("XDG_SESSION_TYPE")}}
                else:
                    return {"error": "WaylandUnsupported", "detail": "Wayland GUI automation is not yet supported (no swaymsg found). Please use X11 for full functionality.", "code": 501}, 501
            if subprocess.call(["which", "wmctrl"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
                return {"error": "MissingTool", "detail": "'wmctrl' is required for Linux GUI actions. Please install it.", "code": 500}, 500
            # Use wmctrl -lG for geometry
            result = subprocess.run("wmctrl -lG -p", shell=True, capture_output=True, text=True)
            xdg_session = os.environ.get("XDG_SESSION_TYPE")
            if result.returncode != 0:
                # Special handling for X11/Wayland/XWayland confusion
                if "_NET_CLIENT_LIST" in result.stderr or "Cannot get client list properties" in result.stderr:
                    return {"error": "X11Unavailable", "detail": "X11 window management is not available: wmctrl could not access _NET_CLIENT_LIST. This usually means you are running under Wayland or XWayland without a compatible X11 window manager. Native Wayland GUI automation is not yet supported.", "code": 501, "env": {"DISPLAY": display, "WAYLAND_DISPLAY": wayland, "XDG_SESSION_TYPE": xdg_session}}, 501
                return {"error": "WmctrlError", "detail": f"wmctrl error: {result.stderr}", "code": 500}, 500
            windows = []
            for line in result.stdout.splitlines():
                # Format: 0x01234567  0 desktop x y w h pid host title
                parts = line.split(None, 8)
                if len(parts) < 9:
                    continue
                win_id, desktop, x, y, w, h, pid, host, title = parts
                # Get window state (minimized, maximized, etc.)
                state = "unknown"
                state_result = subprocess.run(f"xprop -id {win_id} _NET_WM_STATE", shell=True, capture_output=True, text=True)
                if state_result.returncode == 0:
                    state = state_result.stdout.strip()
                windows.append({
                    "window_id": win_id,
                    "desktop": desktop,
                    "pid": pid,
                    "host": host,
                    "title": title,
                    "geometry": {"x": int(x), "y": int(y), "width": int(w), "height": int(h)},
                    "state": state
                })
            return {"windows": windows, "count": len(windows), "env": {"DISPLAY": display, "WAYLAND_DISPLAY": wayland, "XDG_SESSION_TYPE": xdg_session}}
        elif os_type == "Windows":
            # Use PowerShell to enumerate windows with titles
            ps_script = (
                "$windows = Get-Process | Where-Object { $_.MainWindowHandle -ne 0 } | "
                "Select-Object MainWindowHandle,Id,ProcessName,MainWindowTitle; "
                "$windows | ForEach-Object { \"$($_.MainWindowHandle) $($_.Id) $($_.ProcessName) $($_.MainWindowTitle)\" }"
            )
            result = subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True)
            if result.returncode != 0:
                raise HTTPException(status_code=500, detail=f"PowerShell error: {result.stderr}")
            windows = []
            for line in result.stdout.splitlines():
                parts = line.split(None, 3)
                if len(parts) < 4:
                    continue
                handle, pid, proc, title = parts
                windows.append({
                    "window_handle": handle,
                    "pid": pid,
                    "process": proc,
                    "title": title
                })
            return {"windows": windows, "count": len(windows)}
        elif os_type == "Darwin":
            # Use AppleScript to enumerate open windows and their PIDs
            script = (
                'set output to ""\n'
                'tell application "System Events"\n'
                '  set procList to every process whose background only is false\n'
                '  repeat with proc in procList\n'
                '    set procName to name of proc\n'
                '    set procPID to unix id of proc\n'
                '    try\n'
                '      set winList to every window of proc\n'
                '      repeat with w in winList\n'
                '        set winTitle to name of w\n'
                '        set output to output & procPID & ":" & procName & ":" & winTitle & "\n"\n'
                '      end repeat\n'
                '    end try\n'
                '  end repeat\n'
                'end tell\n'
                'return output'
            )
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            if result.returncode != 0:
                raise HTTPException(status_code=500, detail=f"osascript error: {result.stderr}")
            windows = []
            for line in result.stdout.splitlines():
                parts = line.split(":", 2)
                if len(parts) < 3:
                    continue
                pid, proc, title = parts
                windows.append({
                    "pid": pid,
                    "process": proc,
                    "title": title
                })
            return {"windows": windows, "count": len(windows)}



    import shlex
    import shutil
    try:
        if req.action == "launch":
            if not req.app:
                return {"error": "MissingField", "detail": "'app' is required for launch action", "code": 422}, 422
            # Validate app existence
            app_path = shutil.which(req.app)
            if not app_path:
                return {"error": "AppNotFound", "detail": f"Application '{req.app}' not found in PATH", "code": 404}, 404
            # Sanitize args
            if req.args:
                try:
                    args_list = shlex.split(req.args)
                except Exception as e:
                    return {"error": "InvalidArgs", "detail": f"Failed to parse args: {e}", "code": 400}, 400
            else:
                args_list = []
            # Only allow safe args (basic check: no shell metacharacters)
            forbidden = {';', '|', '&', '$', '`', '>', '<', '\\', '&&', '||'}
            if any(any(f in arg for f in forbidden) for arg in args_list):
                return {"error": "UnsafeArgs", "detail": "Arguments contain forbidden shell metacharacters.", "code": 400}, 400
            # Launch app safely
            try:
                subprocess.Popen([app_path] + args_list)
            except Exception as e:
                return {"error": "LaunchFailed", "detail": str(e), "code": 500}, 500
            return {"result": f"Launched {req.app}", "app": req.app, "args": args_list}

        elif req.action == "kill":
            if not req.app:
                return {"error": "MissingField", "detail": "'app' is required for kill action", "code": 422}, 422
            kill_cmd = {
                "Windows": ["taskkill", "/IM", req.app, "/F"],
                "Linux": ["pkill", "-f", req.app],
                "Darwin": ["pkill", "-f", req.app]
            }[platform.system()]
            try:
                subprocess.run(kill_cmd)
            except Exception as e:
                return {"error": "KillFailed", "detail": str(e), "code": 500}, 500
            return {"result": f"Killed {req.app}"}

        elif req.action == "list":
            list_cmd = {
                "Windows": "tasklist",
                "Linux": "ps aux",
                "Darwin": "ps aux"
            }[platform.system()]
            result = subprocess.run(list_cmd, shell=True, capture_output=True, text=True)
            output = result.stdout
            # Filtering
            lines = output.splitlines()
            if req.filter:
                lines = [line for line in lines if req.filter.lower() in line.lower()]
            total = len(lines)
            offset = req.offset if req.offset and req.offset >= 0 else 0
            limit = req.limit if req.limit and req.limit > 0 else 100
            paged = lines[offset:offset+limit]
            truncated = total > (offset + limit)
            result_obj = {
                "items": paged,
                "filter": req.filter,
                "limit": limit,
                "offset": offset,
                "total": total,
                "truncated": truncated
            }
            return {"result": result_obj}

        # --- GUI Interaction Actions ---

        elif req.action in ["focus", "minimize", "maximize", "move", "resize"]:
            os_type = platform.system()
            window_title = req.window_title or req.app
            if not window_title:
                return {"error": "MissingField", "detail": "'window_title' or 'app' is required for GUI actions", "code": 422}, 422

            if os_type == "Linux":
                display = os.environ.get("DISPLAY")
                wayland = os.environ.get("WAYLAND_DISPLAY")
                if not display and not wayland:
                    return {"error": "NoGUISession", "detail": "No GUI session detected (neither DISPLAY nor WAYLAND_DISPLAY set). GUI actions require a running desktop session.", "code": 500}, 500

                if display:
                    if subprocess.call(["which", "wmctrl"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
                        return {"error": "MissingTool", "detail": "'wmctrl' is required for Linux GUI actions. Please install it.", "code": 500}, 500

                    def find_windows(req):
                        list_cmd = f"wmctrl -lp"
                        result = subprocess.run(list_cmd, shell=True, capture_output=True, text=True)
                        xdg_session = os.environ.get("XDG_SESSION_TYPE")
                        if result.returncode != 0:
                            if "_NET_CLIENT_LIST" in result.stderr or "Cannot get client list properties" in result.stderr:
                                return {"error": "X11Unavailable", "detail": "X11 window management is not available: wmctrl could not access _NET_CLIENT_LIST. This usually means you are running under Wayland or XWayland without a compatible X11 window manager. Native Wayland GUI automation is not yet supported.", "code": 501, "env": {"DISPLAY": display, "WAYLAND_DISPLAY": wayland, "XDG_SESSION_TYPE": xdg_session}}, 501
                            return {"error": "WmctrlError", "detail": f"wmctrl error: {result.stderr}", "code": 500}, 500
                        windows = result.stdout.splitlines()
                        matches = []
                        if req.pid:
                            for line in windows:
                                parts = line.split()
                                if len(parts) > 2 and str(req.pid) == parts[2]:
                                    matches.append((parts[0], line))
                        elif req.window_title:
                            for line in windows:
                                if req.window_title.lower() in line.lower():
                                    matches.append((line.split()[0], line))
                        elif req.app:
                            for line in windows:
                                if req.app.lower() in line.lower():
                                    matches.append((line.split()[0], line))
                        return matches

                    matches = find_windows(req)
                    if isinstance(matches, tuple):
                        return matches
                    if not matches:
                        return {"error": "WindowNotFound", "detail": f"No window found matching title='{req.window_title}', app='{req.app}', pid='{req.pid}'", "code": 404}, 404
                    idx = req.window_index if req.window_index is not None else 0
                    if idx < 0 or idx >= len(matches):
                        return {"error": "WindowIndexOutOfRange", "detail": f"window_index {idx} out of range for {len(matches)} matches", "code": 400}, 400
                    win_id, win_line = matches[idx]
                    if req.action == "focus":
                        cmd = f"wmctrl -ia {win_id}"
                    elif req.action == "minimize":
                        cmd = f"wmctrl -ir {win_id} -b add,hidden"
                    elif req.action == "maximize":
                        cmd = f"wmctrl -ir {win_id} -b add,maximized_vert,maximized_horz"
                    elif req.action == "move":
                        if req.x is None or req.y is None:
                            return {"error": "MissingField", "detail": "'x' and 'y' required for move action", "code": 422}, 422
                        cmd = f"wmctrl -ir {win_id} -e 0,{req.x},{req.y},-1,-1"
                    elif req.action == "resize":
                        if req.width is None or req.height is None:
                            return {"error": "MissingField", "detail": "'width' and 'height' required for resize action", "code": 422}, 422
                        cmd = f"wmctrl -ir {win_id} -e 0,-1,-1,{req.width},{req.height}"
                    else:
                        return {"error": "UnknownGUIAction", "detail": "Unknown GUI action", "code": 400}, 400
                    result2 = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    if result2.returncode != 0:
                        if "_NET_CLIENT_LIST" in result2.stderr or "Cannot get client list properties" in result2.stderr:
                            return {"error": "X11Unavailable", "detail": "X11 window management is not available: wmctrl could not access _NET_CLIENT_LIST. This usually means you are running under Wayland or XWayland without a compatible X11 window manager. Native Wayland GUI automation is not yet supported.", "code": 501, "env": {"DISPLAY": display, "WAYLAND_DISPLAY": wayland, "XDG_SESSION_TYPE": xdg_session}}, 501
                        return {"error": "WmctrlError", "detail": f"wmctrl error: {result2.stderr}\nWindow: {win_line}", "code": 500}, 500
                    return {"result": f"{req.action} action performed on window (id {win_id}): {win_line}", "matches": [m[1] for m in matches], "window_index": idx}


                # Wayland support (experimental, Sway/wlroots only):
                if wayland:
                    import shutil
                    if shutil.which("swaymsg"):
                        import json
                        def get_sway_windows():
                            result = subprocess.run(["swaymsg", "-t", "get_tree"], capture_output=True, text=True)
                            if result.returncode != 0:
                                raise HTTPException(status_code=500, detail=f"swaymsg error: {result.stderr}")
                            try:
                                tree = json.loads(result.stdout)
                            except Exception as e:
                                raise HTTPException(status_code=500, detail=f"swaymsg JSON error: {e}")
                            def collect_windows(node, windows):
                                if node.get("type") == "con" and node.get("window_properties"):
                                    windows.append(node)
                                for child in node.get("nodes", []) + node.get("floating_nodes", []):
                                    collect_windows(child, windows)
                            windows = []
                            collect_windows(tree, windows)
                            return windows

                        if req.action == "list_windows":
                            windows = get_sway_windows()
                            formatted = []
                            for win in windows:
                                formatted.append({
                                    "window_id": win.get("id"),
                                    "app_id": win.get("app_id"),
                                    "pid": win.get("pid"),
                                    "title": win.get("name"),
                                    "rect": win.get("rect"),
                                    "window_properties": win.get("window_properties"),
                                })
                            return {"windows": formatted, "count": len(formatted), "env": {"WAYLAND_DISPLAY": wayland, "XDG_SESSION_TYPE": os.environ.get("XDG_SESSION_TYPE")}}
                        elif req.action in ["focus", "minimize", "maximize", "move", "resize"]:
                            windows = get_sway_windows()
                            matches = []
                            for win in windows:
                                if req.window_title and req.window_title.lower() in (win.get("name") or "").lower():
                                    matches.append(win)
                                elif req.app and req.app.lower() in (win.get("app_id") or "").lower():
                                    matches.append(win)
                            if not matches:
                                raise HTTPException(status_code=404, detail="No matching window found for action on Wayland/Sway")
                            idx = req.window_index if req.window_index is not None else 0
                            if idx < 0 or idx >= len(matches):
                                raise HTTPException(status_code=400, detail=f"window_index {idx} out of range for {len(matches)} matches")
                            win_id = matches[idx]["id"]
                            if req.action == "focus":
                                sway_cmd = ["swaymsg", f"[con_id={win_id}] focus"]
                            elif req.action == "minimize":
                                sway_cmd = ["swaymsg", f"[con_id={win_id}] minimize"]
                            elif req.action == "maximize":
                                sway_cmd = ["swaymsg", f"[con_id={win_id}] fullscreen enable"]
                            elif req.action == "move":
                                if req.x is None or req.y is None:
                                    raise HTTPException(status_code=422, detail="'x' and 'y' required for move action")
                                sway_cmd = ["swaymsg", f"[con_id={win_id}] move position {req.x} {req.y}"]
                            elif req.action == "resize":
                                if req.width is None or req.height is None:
                                    raise HTTPException(status_code=422, detail="'width' and 'height' required for resize action")
                                sway_cmd = ["swaymsg", f"[con_id={win_id}] resize set {req.width} {req.height}"]
                            else:
                                raise HTTPException(status_code=400, detail="Unknown GUI action for Sway")
                            result2 = subprocess.run(sway_cmd, capture_output=True, text=True)
                            if result2.returncode != 0:
                                raise HTTPException(status_code=500, detail=f"swaymsg error: {result2.stderr}")
                            return {"result": f"{req.action} action performed on window (id {win_id})", "window_index": idx}
                        else:
                            raise HTTPException(status_code=501, detail="Only 'list_windows', 'focus', 'minimize', 'maximize', 'move', 'resize' are supported for Wayland/Sway (swaymsg)")
                    else:
                        raise HTTPException(status_code=501, detail="Wayland GUI automation is not yet supported (no swaymsg found). Please use X11 for full functionality.")


            elif os_type == "Darwin":
                # macOS: Use osascript (AppleScript) for window management
                def run_osascript(script):
                    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
                    if result.returncode != 0:
                        raise HTTPException(status_code=500, detail=f"osascript error: {result.stderr}")
                    return result.stdout.strip()

                # AppleScript window targeting by app name (not always by window title)
                app_name = window_title
                if req.action == "focus":
                    script = f'tell application "{app_name}" to activate'
                elif req.action == "minimize":
                    script = f'tell application "System Events" to set miniaturized of windows of process "{app_name}" to true'
                elif req.action == "maximize":
                    # Maximize: set window bounds to screen bounds
                    script = (
                        'tell application "System Events"\n'
                        f'  set frontApp to first process whose name is "{app_name}"\n'
                        '  tell front window of frontApp\n'
                        '    set position to {0, 22}\n'  # 22 for menu bar
                        '    set size to {1440, 900}\n'  # Default size, ideally get screen size
                        '  end tell\n'
                        'end tell'
                    )
                elif req.action == "move":
                    if req.x is None or req.y is None:
                        raise HTTPException(status_code=422, detail="'x' and 'y' required for move action")
                    script = (
                        'tell application "System Events"\n'
                        f'  set frontApp to first process whose name is "{app_name}"\n'
                        '  tell front window of frontApp\n'
                        f'    set position to {{{req.x}, {req.y}}}\n'
                        '  end tell\n'
                        'end tell'
                    )
                elif req.action == "resize":
                    if req.width is None or req.height is None:
                        raise HTTPException(status_code=422, detail="'width' and 'height' required for resize action")
                    script = (
                        'tell application "System Events"\n'
                        f'  set frontApp to first process whose name is "{app_name}"\n'
                        '  tell front window of frontApp\n'
                        f'    set size to {{{req.width}, {req.height}}}\n'
                        '  end tell\n'
                        'end tell'
                    )
                else:
                    raise HTTPException(status_code=400, detail="Unknown GUI action")
                run_osascript(script)
                return {"result": f"{req.action} action performed on '{app_name}' (macOS)"}

            elif os_type == "Windows":
                # Windows: Use PowerShell for window management (requires window title)
                def run_powershell(ps_script):
                    result = subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True)
                    if result.returncode != 0:
                        raise HTTPException(status_code=500, detail=f"PowerShell error: {result.stderr}")
                    return result.stdout.strip()

                # PowerShell window targeting by title (partial match)
                title = window_title
                if req.action == "focus":
                    ps_script = f"Add-Type @'\nusing System;\nusing System.Runtime.InteropServices;\npublic class Win32 {{\n[DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr hWnd);\n}}\n'@; $hwnd = Get-Process | Where-Object {{$_.MainWindowTitle -like '*{title}*'}} | Select-Object -First 1 -ExpandProperty MainWindowHandle; [void][Win32]::SetForegroundWindow($hwnd)"
                elif req.action == "minimize":
                    ps_script = f"Add-Type @'\nusing System;\nusing System.Runtime.InteropServices;\npublic class Win32 {{\n[DllImport(\"user32.dll\")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);\n}}\n'@; $hwnd = Get-Process | Where-Object {{$_.MainWindowTitle -like '*{title}*'}} | Select-Object -First 1 -ExpandProperty MainWindowHandle; [void][Win32]::ShowWindowAsync($hwnd, 2)"  # 2 = SW_MINIMIZE
                elif req.action == "maximize":
                    ps_script = f"Add-Type @'\nusing System;\nusing System.Runtime.InteropServices;\npublic class Win32 {{\n[DllImport(\"user32.dll\")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);\n}}\n'@; $hwnd = Get-Process | Where-Object {{$_.MainWindowTitle -like '*{title}*'}} | Select-Object -First 1 -ExpandProperty MainWindowHandle; [void][Win32]::ShowWindowAsync($hwnd, 3)"  # 3 = SW_MAXIMIZE
                elif req.action == "move":
                    if req.x is None or req.y is None:
                        raise HTTPException(status_code=422, detail="'x' and 'y' required for move action")
                    ps_script = f"Add-Type @'\nusing System;\nusing System.Runtime.InteropServices;\npublic class Win32 {{\n[DllImport(\"user32.dll\")] public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);\n}}\n'@; $proc = Get-Process | Where-Object {{$_.MainWindowTitle -like '*{title}*'}} | Select-Object -First 1; $hwnd = $proc.MainWindowHandle; [void][Win32]::MoveWindow($hwnd, {req.x}, {req.y}, $proc.MainWindowHandle.Width, $proc.MainWindowHandle.Height, $true)"
                elif req.action == "resize":
                    if req.width is None or req.height is None:
                        raise HTTPException(status_code=422, detail="'width' and 'height' required for resize action")
                    ps_script = f"Add-Type @'\nusing System;\nusing System.Runtime.InteropServices;\npublic class Win32 {{\n[DllImport(\"user32.dll\")] public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);\n}}\n'@; $proc = Get-Process | Where-Object {{$_.MainWindowTitle -like '*{title}*'}} | Select-Object -First 1; $hwnd = $proc.MainWindowHandle; [void][Win32]::MoveWindow($hwnd, $proc.MainWindowHandle.X, $proc.MainWindowHandle.Y, {req.width}, {req.height}, $true)"
                else:
                    raise HTTPException(status_code=400, detail="Unknown GUI action")
                run_powershell(ps_script)
                return {"result": f"{req.action} action performed on window '{title}' (Windows)"}

            else:
                raise HTTPException(status_code=501, detail="Unsupported OS for GUI actions")

        else:
            return {"error": "InvalidAction", "detail": "Invalid action", "code": 400}, 400

    except HTTPException as e:
        # FastAPI HTTPException: return as structured error
        return {"error": "HTTPException", "detail": str(e.detail), "code": e.status_code}, e.status_code
    except Exception as e:
        return {"error": "InternalServerError", "detail": str(e), "code": 500}, 500
