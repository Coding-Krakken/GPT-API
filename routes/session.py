"""
Remote session management endpoints for GUI automation.
Provides RDP, VNC, and headless session support for distributed automation.
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import time
import json
import os
import platform
import subprocess
import threading
from utils.auth import verify_key
from utils.safety import safety_check, log_action

router = APIRouter()

# Session registry to track active remote sessions
_sessions = {}
_sessions_lock = threading.Lock()

class SessionStartRequest(BaseModel):
    action: str
    session_type: str  # "rdp", "vnc", "headless", "x11vnc"
    display: Optional[str] = ":1"  # Display number for X11/VNC
    geometry: Optional[str] = "1920x1080"  # Screen resolution
    depth: Optional[int] = 24  # Color depth
    host: Optional[str] = "localhost"  # Remote host for RDP
    port: Optional[int] = None  # Port override
    username: Optional[str] = None  # Remote username
    password: Optional[str] = None  # Remote password (use with caution)
    dry_run: Optional[bool] = False

class SessionConfigRequest(BaseModel):
    action: str
    session_id: str
    display_config: Optional[Dict[str, Any]] = None
    performance_config: Optional[Dict[str, Any]] = None
    security_config: Optional[Dict[str, Any]] = None
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

def _generate_session_id() -> str:
    """Generate unique session ID"""
    import uuid
    return str(uuid.uuid4())[:8]

def _check_display_available(display: str) -> bool:
    """Check if X11 display is available"""
    try:
        result = subprocess.run(
            ["xdpyinfo", "-display", display],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except:
        return False

def _start_xvfb_session(display: str, geometry: str, depth: int) -> Dict[str, Any]:
    """Start Xvfb (X Virtual Framebuffer) session for headless GUI"""
    try:
        # Check if Xvfb is available
        if not os.path.exists("/usr/bin/Xvfb"):
            return {"success": False, "error": "Xvfb not installed"}
        
        # Start Xvfb
        cmd = [
            "Xvfb", display,
            "-screen", "0", f"{geometry}x{depth}",
            "-ac", "+extension", "GLX"
        ]
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait a moment for server to start
        time.sleep(2)
        
        # Check if it's running
        if process.poll() is None and _check_display_available(display):
            return {
                "success": True,
                "process": process,
                "display": display,
                "geometry": geometry,
                "depth": depth
            }
        else:
            process.terminate()
            return {"success": False, "error": "Failed to start Xvfb"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def _start_vnc_session(display: str, geometry: str, depth: int, port: Optional[int] = None) -> Dict[str, Any]:
    """Start VNC server session"""
    try:
        # Try different VNC servers
        vnc_servers = [
            ("x11vnc", [
                "x11vnc", "-display", display, "-forever", "-nopw",
                "-rfbport", str(port or 5901)
            ]),
            ("tigervncserver", [
                "vncserver", display, "-geometry", geometry, "-depth", str(depth)
            ])
        ]
        
        for server_name, cmd in vnc_servers:
            if os.path.exists(f"/usr/bin/{server_name.split()[0]}"):
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                time.sleep(2)
                
                if process.poll() is None:
                    return {
                        "success": True,
                        "process": process,
                        "server": server_name,
                        "display": display,
                        "port": port or 5901,
                        "geometry": geometry
                    }
                else:
                    process.terminate()
        
        return {"success": False, "error": "No VNC server available"}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def _start_rdp_session(host: str, username: str, password: str, port: Optional[int] = None) -> Dict[str, Any]:
    """Start RDP client session"""
    try:
        # This would typically use xfreerdp or rdesktop
        # For security, we'll just simulate the connection
        return {
            "success": True,
            "host": host,
            "port": port or 3389,
            "username": username,
            "type": "rdp",
            "note": "RDP session simulation - real implementation would use xfreerdp"
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/start", dependencies=[Depends(verify_key)])
def start_session(req: SessionStartRequest, response: Response):
    """
    Start remote GUI session (RDP, VNC, headless).
    Enables automation in remote or virtual environments.
    """
    start_time = time.time()
    
    if req.action != "start":
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    # Safety check
    safety_result = safety_check("/session", req.action, req.dict(), req.dry_run)
    if not safety_result["safe"]:
        return _error_response("SAFETY_VIOLATION", safety_result["message"], {"safety": safety_result})
    
    valid_types = ["rdp", "vnc", "headless", "x11vnc"]
    if req.session_type not in valid_types:
        return _error_response("INVALID_SESSION_TYPE", f"session_type must be one of: {valid_types}")
    
    session_id = _generate_session_id()
    
    result = {
        "session_id": session_id,
        "session_type": req.session_type,
        "display": req.display,
        "geometry": req.geometry,
        "depth": req.depth,
        "dry_run": req.dry_run,
        "safety_check": safety_result
    }
    
    if req.dry_run:
        result["status"] = "would_start"
        log_action("/session", req.action, req.dict(), result, dry_run=True)
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
    
    try:
        session_info = {"id": session_id, "type": req.session_type, "started_at": time.time()}
        
        if req.session_type == "headless":
            session_result = _start_xvfb_session(req.display, req.geometry, req.depth)
            session_info.update(session_result)
            
        elif req.session_type in ["vnc", "x11vnc"]:
            # First start Xvfb if needed
            if not _check_display_available(req.display):
                xvfb_result = _start_xvfb_session(req.display, req.geometry, req.depth)
                if not xvfb_result["success"]:
                    return _error_response("XVFB_START_FAILED", xvfb_result["error"])
                session_info["xvfb"] = xvfb_result
            
            # Then start VNC
            vnc_result = _start_vnc_session(req.display, req.geometry, req.depth, req.port)
            session_info.update(vnc_result)
            
        elif req.session_type == "rdp":
            if not req.host or not req.username:
                return _error_response("MISSING_RDP_CREDENTIALS", "host and username required for RDP")
            rdp_result = _start_rdp_session(req.host, req.username, req.password or "", req.port)
            session_info.update(rdp_result)
        
        if session_info.get("success", True):
            with _sessions_lock:
                _sessions[session_id] = session_info
            
            result.update({
                "status": "started",
                "session_info": {k: v for k, v in session_info.items() if k not in ["process", "password"]}
            })
            
            log_action("/session", req.action, req.dict(), result, dry_run=False)
            
            return {
                "result": result,
                "timestamp": int(time.time() * 1000),
                "latency_ms": int((time.time() - start_time) * 1000)
            }
        else:
            return _error_response("SESSION_START_FAILED", session_info.get("error", "Unknown error"))
            
    except Exception as e:
        return _error_response("SESSION_ERROR", str(e))

@router.post("/config", dependencies=[Depends(verify_key)])
def configure_session(req: SessionConfigRequest, response: Response):
    """
    Configure remote session parameters.
    Adjust display, performance, and security settings.
    """
    start_time = time.time()
    
    if req.action != "configure":
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    # Safety check
    safety_result = safety_check("/session", req.action, req.dict(), req.dry_run)
    if not safety_result["safe"]:
        return _error_response("SAFETY_VIOLATION", safety_result["message"], {"safety": safety_result})
    
    with _sessions_lock:
        if req.session_id not in _sessions:
            return _error_response("SESSION_NOT_FOUND", f"Session {req.session_id} not found")
        
        session_info = _sessions[req.session_id]
    
    result = {
        "session_id": req.session_id,
        "action": req.action,
        "display_config": req.display_config,
        "performance_config": req.performance_config,
        "security_config": req.security_config,
        "dry_run": req.dry_run,
        "safety_check": safety_result
    }
    
    if req.dry_run:
        result["status"] = "would_configure"
        log_action("/session", req.action, req.dict(), result, dry_run=True)
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
    
    try:
        # Apply configuration changes
        if req.display_config:
            session_info["display_config"] = req.display_config
        if req.performance_config:
            session_info["performance_config"] = req.performance_config
        if req.security_config:
            session_info["security_config"] = req.security_config
        
        result["status"] = "configured"
        log_action("/session", req.action, req.dict(), result, dry_run=False)
        
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return _error_response("CONFIG_ERROR", str(e))

@router.get("/list", dependencies=[Depends(verify_key)])
def list_sessions():
    """List all active remote sessions"""
    with _sessions_lock:
        sessions = []
        for session_id, info in _sessions.items():
            # Remove sensitive information
            safe_info = {
                "session_id": session_id,
                "type": info.get("type"),
                "display": info.get("display"),
                "started_at": info.get("started_at"),
                "status": "active" if info.get("process") and info["process"].poll() is None else "inactive"
            }
            sessions.append(safe_info)
    
    return {
        "result": {
            "sessions": sessions,
            "total": len(sessions)
        },
        "timestamp": int(time.time() * 1000)
    }

@router.post("/stop", dependencies=[Depends(verify_key)])
def stop_session(session_id: str, response: Response):
    """Stop remote session and cleanup resources"""
    start_time = time.time()
    
    with _sessions_lock:
        if session_id not in _sessions:
            return _error_response("SESSION_NOT_FOUND", f"Session {session_id} not found")
        
        session_info = _sessions[session_id]
        
        # Stop processes
        try:
            if "process" in session_info and session_info["process"]:
                session_info["process"].terminate()
                time.sleep(1)
                if session_info["process"].poll() is None:
                    session_info["process"].kill()
            
            if "xvfb" in session_info and "process" in session_info["xvfb"]:
                session_info["xvfb"]["process"].terminate()
                
        except Exception as e:
            pass  # Process might already be stopped
        
        del _sessions[session_id]
    
    result = {
        "session_id": session_id,
        "status": "stopped"
    }
    
    log_action("/session", "stop", {"session_id": session_id}, result, dry_run=False)
    
    return {
        "result": result,
        "timestamp": int(time.time() * 1000),
        "latency_ms": int((time.time() - start_time) * 1000)
    }

@router.get("/capabilities", dependencies=[Depends(verify_key)])
def get_session_capabilities():
    """Get available session management capabilities"""
    capabilities = {
        "platform": platform.system(),
        "headless": os.path.exists("/usr/bin/Xvfb"),
        "vnc_servers": [],
        "rdp_clients": [],
        "display_management": True,
        "session_types": ["headless"]
    }
    
    # Check for VNC servers
    vnc_servers = ["x11vnc", "vncserver", "tigervncserver"]
    for server in vnc_servers:
        if os.path.exists(f"/usr/bin/{server}"):
            capabilities["vnc_servers"].append(server)
            if "vnc" not in capabilities["session_types"]:
                capabilities["session_types"].append("vnc")
    
    # Check for RDP clients
    rdp_clients = ["xfreerdp", "rdesktop"]
    for client in rdp_clients:
        if os.path.exists(f"/usr/bin/{client}"):
            capabilities["rdp_clients"].append(client)
            if "rdp" not in capabilities["session_types"]:
                capabilities["session_types"].append("rdp")
    
    return {
        "result": capabilities,
        "timestamp": int(time.time() * 1000)
    }