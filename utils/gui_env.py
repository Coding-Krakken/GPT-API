import os
import shutil
import platform
import subprocess
import json
import time
import re
from typing import Dict, List, Any, Optional
from utils.security import safe_subprocess_run

# Optional imports with fallbacks
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Warning: psutil not available. Some process detection features will be limited.")

def get_microsecond_timestamp():
    """Get current timestamp with microsecond precision"""
    return int(time.time() * 1000000)

def calculate_latency_us(start_time_us):
    """Calculate latency in microseconds"""
    return get_microsecond_timestamp() - start_time_us

def run_with_observability(command, timeout=10):
    """Run command with full observability and error capture - SECURE VERSION"""
    return safe_subprocess_run(command, timeout=timeout)

def get_process_list_fallback():
    """Fallback process detection without psutil"""
    processes = []
    try:
        # Try using ps command as fallback
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            for line in result.stdout.split('\n')[1:]:  # Skip header
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 11:
                        try:
                            processes.append({
                                'pid': int(parts[1]),
                                'name': parts[10],
                                'command': ' '.join(parts[10:])
                            })
                        except (ValueError, IndexError):
                            continue
    except Exception:
        pass
    return processes

def detect_gui_environment_comprehensive():
    """Comprehensive GUI environment detection with Wayland/X11 hybrid support"""
    start_time = get_microsecond_timestamp()
    
    os_type = platform.system()
    env = {
        "os": os_type,
        "wayland": False,
        "x11": False,
        "display": os.environ.get("DISPLAY"),
        "wayland_display": os.environ.get("WAYLAND_DISPLAY"),
        "session_type": os.environ.get("XDG_SESSION_TYPE"),
        "desktop_session": os.environ.get("XDG_CURRENT_DESKTOP"),
        "compositor": None,
        "wmctrl": False,
        "xprop": False,
        "swaymsg": False,
        "xvfb": False,
        "vnc": False,
        "vnc_display": None,
        "test_mode": os.environ.get("GUI_TEST_MODE") == "1",
        "missing_tools": [],
        "detection_methods": [],
        "tools": {},
        "capabilities": {
            "window_management": False,
            "wayland_introspection": False,
            "x11_fallback": False,
            "screenshot": False,
            "input_automation": False,
            "accessibility": False
        },
        "detection_latency_us": 0
    }
    
    if os_type == "Linux":
        # Enhanced tool detection
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
            available = bool(shutil.which(tool))
            env["tools"][tool] = available
            # Set legacy fields for backward compatibility
            if tool in ["wmctrl", "xprop", "swaymsg", "xvfb"]:
                env[tool] = available
            if not available and tool in ["wmctrl", "xprop", "Xvfb", "vncserver", "x11vnc"]:
                env["missing_tools"].append(tool)
        
        # Session type detection
        env["wayland"] = bool(env["wayland_display"])
        env["x11"] = bool(env["display"])
        
        if env["wayland"]:
            env["detection_methods"].append("WAYLAND_DISPLAY_env")
            
            # Detect Wayland compositor
            if env["tools"]["swaymsg"]:
                try:
                    result = run_with_observability("swaymsg -t get_version", timeout=5)
                    if result["exit_code"] == 0:
                        env["compositor"] = "sway"
                        env["capabilities"]["window_management"] = True
                        env["detection_methods"].append("swaymsg_version")
                except:
                    pass
            
            # Check for other Wayland compositors via process detection
            compositor_names = ["gnome-shell", "kwin_wayland", "weston", "hyprland", "mutter"]
            
            if PSUTIL_AVAILABLE:
                try:
                    for proc in psutil.process_iter(['name']):
                        if proc.info['name']:
                            for compositor in compositor_names:
                                if compositor in proc.info['name']:
                                    env["compositor"] = compositor
                                    env["detection_methods"].append(f"process_{compositor}")
                                    break
                        if env["compositor"]:
                            break
                except:
                    pass
            else:
                # Fallback using ps command
                processes = get_process_list_fallback()
                for proc in processes:
                    for compositor in compositor_names:
                        if compositor in proc['name']:
                            env["compositor"] = compositor
                            env["detection_methods"].append(f"process_{compositor}_fallback")
                            break
                    if env["compositor"]:
                        break
            
            # Wayland capabilities
            if env["tools"]["wlr-randr"]:
                env["capabilities"]["wayland_introspection"] = True
            
            # Check for XWayland fallback
            if env["display"] and (env["tools"]["wmctrl"] or env["tools"]["xprop"]):
                env["capabilities"]["x11_fallback"] = True
                env["detection_methods"].append("xwayland_detected")
                
        elif env["x11"]:
            env["detection_methods"].append("DISPLAY_env")
            
            # X11 capabilities
            if env["tools"]["wmctrl"] and env["tools"]["xprop"]:
                env["capabilities"]["window_management"] = True
            
            # Detect X11 window manager
            try:
                result = run_with_observability("xprop -root _NET_WM_NAME", timeout=5)
                if result["exit_code"] == 0 and result["stdout"]:
                    wm_match = re.search(r'"([^"]+)"', result["stdout"])
                    if wm_match:
                        env["compositor"] = wm_match.group(1)
                        env["detection_methods"].append("xprop_wm_name")
            except:
                pass
        
        # Desktop portal detection for cross-platform screenshot/automation
        portal_tools = ["xdg-desktop-portal-kde", "xdg-desktop-portal-gnome", "xdg-desktop-portal-wlr"]
        if any(env["tools"][tool] for tool in portal_tools):
            env["capabilities"]["screenshot"] = True
            env["capabilities"]["input_automation"] = True
            env["detection_methods"].append("desktop_portal")
        
        # Screenshot capabilities
        screenshot_tools = ["scrot", "gnome-screenshot", "spectacle", "xdotool"]
        if any(env["tools"][tool] for tool in screenshot_tools):
            env["capabilities"]["screenshot"] = True
        
        # Input automation capabilities  
        input_tools = ["xdotool", "ydotool", "xvkbd"]
        if any(env["tools"][tool] for tool in input_tools):
            env["capabilities"]["input_automation"] = True
            
        # Accessibility capabilities
        if env["tools"]["at-spi2-core"]:
            env["capabilities"]["accessibility"] = True
        
        # Detect running VNC server (TigerVNC, x11vnc, etc.)
        vnc_display = None
        for d in [":1", ":2", ":0"]:
            if os.path.exists(f"/tmp/.X11-unix/X{d[1:]}"):
                vnc_display = d
                break
        env["vnc"] = vnc_display is not None
        env["vnc_display"] = vnc_display
        
        # Set gui flag for backward compatibility
        env["gui"] = env["capabilities"]["window_management"] or env["x11"] or env["wayland"]
    
    env["detection_latency_us"] = calculate_latency_us(start_time)
    return env

def detect_gui_environment():
    """
    Legacy function - maintained for backward compatibility
    """
    comprehensive_env = detect_gui_environment_comprehensive()
    
    # Return simplified structure for backward compatibility
    return {
        "os": comprehensive_env["os"],
        "wayland": comprehensive_env["wayland"],
        "x11": comprehensive_env["x11"],
        "display": comprehensive_env["display"],
        "wayland_display": comprehensive_env["wayland_display"],
        "session_type": comprehensive_env["session_type"],
        "wmctrl": comprehensive_env["wmctrl"],
        "xprop": comprehensive_env["xprop"],
        "swaymsg": comprehensive_env["swaymsg"],
        "xvfb": comprehensive_env["xvfb"],
        "vnc": comprehensive_env["vnc"],
        "vnc_display": comprehensive_env["vnc_display"],
        "test_mode": comprehensive_env["test_mode"],
        "missing_tools": comprehensive_env["missing_tools"],
        "gui": comprehensive_env.get("gui", False)
    }

def get_install_guidance(missing_tools):
    if not missing_tools:
        return None
    
    guidance_map = {
        "wmctrl": "sudo apt install wmctrl",
        "xprop": "sudo apt install x11-utils", 
        "xwininfo": "sudo apt install x11-utils",
        "xdotool": "sudo apt install xdotool",
        "swaymsg": "sudo apt install sway",
        "wlr-randr": "sudo apt install wlr-randr",
        "wayland-info": "sudo apt install wayland-utils",
        "xdg-desktop-portal-kde": "sudo apt install xdg-desktop-portal-kde",
        "xdg-desktop-portal-gnome": "sudo apt install xdg-desktop-portal-gnome", 
        "xdg-desktop-portal-wlr": "sudo apt install xdg-desktop-portal-wlr",
        "Xvfb": "sudo apt install xvfb",
        "vncserver": "sudo apt install tigervnc-standalone-server",
        "x11vnc": "sudo apt install x11vnc",
        "scrot": "sudo apt install scrot",
        "gnome-screenshot": "sudo apt install gnome-screenshot",
        "spectacle": "sudo apt install spectacle",
        "xvkbd": "sudo apt install xvkbd",
        "ydotool": "sudo apt install ydotool",
        "at-spi2-core": "sudo apt install at-spi2-core"
    }
    
    install_commands = []
    for tool in missing_tools:
        if tool in guidance_map:
            install_commands.append(guidance_map[tool])
    
    if install_commands:
        return (
            f"Missing required GUI tools: {', '.join(missing_tools)}. "
            f"Install with: {'; '.join(install_commands)}"
        )
    
    return (
        "Missing required GUI tools: " + ", ".join(missing_tools) + ". "
        "Install with: sudo apt install " + " ".join([t for t in missing_tools if t != 'vncserver']) + ". "
        "For vncserver: sudo apt install tigervnc-standalone-server or similar."
    )

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
