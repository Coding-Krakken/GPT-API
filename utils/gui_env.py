import os
import shutil
import platform
import subprocess

def detect_gui_environment():
    """
    Detects the current GUI environment and returns a dict with details about X11/Wayland, VNC, and tool availability.
    """
    os_type = platform.system()
    env = {
        "os": os_type,
        "wayland": False,
        "x11": False,
        "display": os.environ.get("DISPLAY"),
        "wayland_display": os.environ.get("WAYLAND_DISPLAY"),
        "session_type": os.environ.get("XDG_SESSION_TYPE"),
        "wmctrl": False,
        "xprop": False,
        "swaymsg": False,
        "xvfb": False,
        "vnc": False,
        "vnc_display": None,
        "test_mode": os.environ.get("GUI_TEST_MODE") == "1",
        "missing_tools": [],
    }
    if os_type == "Linux":
        env["wayland"] = bool(env["wayland_display"])
        env["x11"] = bool(env["display"])
        env["wmctrl"] = bool(shutil.which("wmctrl"))
        env["xprop"] = bool(shutil.which("xprop"))
        env["swaymsg"] = bool(shutil.which("swaymsg"))
        env["xvfb"] = bool(shutil.which("Xvfb"))
        # Detect running VNC server (TigerVNC, x11vnc, etc.)
        vnc_display = None
        for d in [":1", ":2", ":0"]:
            if os.path.exists(f"/tmp/.X11-unix/X{d[1:]}"):
                vnc_display = d
                break
        env["vnc"] = vnc_display is not None
        env["vnc_display"] = vnc_display
        # Dependency check
        for tool in ["wmctrl", "xprop", "Xvfb", "vncserver", "x11vnc"]:
            if not shutil.which(tool):
                env["missing_tools"].append(tool)
def get_install_guidance(missing_tools):
    if not missing_tools:
        return None
    return (
        "Missing required GUI tools: " + ", ".join(missing_tools) + ". "
        "Install with: sudo apt install " + " ".join([t for t in missing_tools if t != 'vncserver']) + ". "
        "For vncserver: sudo apt install tigervnc-standalone-server or similar."
    )
    return env or {}

def ensure_x11_or_fail():
    """
    Checks if X11 and required tools are available. Raises HTTPException if not. Falls back to VNC/X11 if available.
    """
    env = detect_gui_environment()
    if env["os"] != "Linux":
        return  # Only enforce on Linux
    # Try X11 first
    if env["x11"] and env["wmctrl"]:
        return
    # Try VNC fallback
    if env["vnc"]:
        os.environ["DISPLAY"] = env["vnc_display"]
        if shutil.which("wmctrl"):
            print("[GUI Fallback] Using running VNC server for fallback X11.")
            return
    # Try to start a VNC server automatically
    started = start_vnc_server(":1")
    if started:
        # Re-detect after starting VNC
        env = detect_gui_environment()
        if env["vnc"]:
            os.environ["DISPLAY"] = env["vnc_display"]
            if shutil.which("wmctrl"):
                print("[GUI Fallback] Started VNC server and set DISPLAY for fallback.")
                return
    # If still not available, raise error with install guidance
    msg = (
        "🛑 GUI Stress-Test Aborted – Incompatible Windowing System Detected\n\n"
        "Your system is running under Wayland or missing X11 tools. "
        "Full GUI automation requires X11 (wmctrl/xprop).\n\n"
        f"Detected: DISPLAY={env['display']} WAYLAND_DISPLAY={env['wayland_display']} XDG_SESSION_TYPE={env['session_type']}\n\n"
        f"Missing tools: {', '.join(env['missing_tools']) if env['missing_tools'] else 'None'}\n"
        f"{get_install_guidance(env['missing_tools']) or ''}\n"
        "To enable full GUI automation, switch to an X11 session, start a VNC/X11 server, or ensure wmctrl/xprop are installed.\n"
    )
    from fastapi import HTTPException
    raise HTTPException(status_code=400, detail=msg)
def log_full_gui_env():
    env = detect_gui_environment() or {}
    # Defensive: always return a dict with all keys, even if env is incomplete
    return {
        "DISPLAY": env.get("display"),
        "WAYLAND_DISPLAY": env.get("wayland_display"),
        "XDG_SESSION_TYPE": env.get("session_type"),
        "os": env.get("os"),
        "x11": env.get("x11"),
        "wayland": env.get("wayland"),
        "wmctrl": env.get("wmctrl"),
        "xprop": env.get("xprop"),
        "swaymsg": env.get("swaymsg"),
        "xvfb": env.get("xvfb"),
        "vnc": env.get("vnc"),
        "vnc_display": env.get("vnc_display"),
        "missing_tools": env.get("missing_tools", []),
        "test_mode": env.get("test_mode"),
    }

def start_vnc_server(display=":1"):
    """
    Attempts to start a VNC server on the given display if not already running.
    Returns True if started or already running, False otherwise.
    """
    if os.path.exists(f"/tmp/.X11-unix/X{display[1:]}"):
        return True  # Already running
    # Try to start TigerVNC
    vnc_cmd = shutil.which("vncserver")
    if vnc_cmd:
        try:
            subprocess.Popen([vnc_cmd, display])
            return True
        except Exception:
            pass
    # Try to start x11vnc (requires running X11 session)
    x11vnc_cmd = shutil.which("x11vnc")
    if x11vnc_cmd:
        try:
            subprocess.Popen([x11vnc_cmd, "-display", display])
            return True
        except Exception:
            pass
    return False
