"""
Clipboard and data transfer endpoints for GUI automation.
Provides text, image, and file clipboard operations with drag-drop support.
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union
import time
import json
import base64
import os
import tempfile
from utils.auth import verify_key
from utils.safety import safety_check, log_action

router = APIRouter()

# Clipboard abstraction - try different clipboard libraries
CLIPBOARD_AVAILABLE = False
_clipboard_impl = None

try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
    _clipboard_impl = "pyperclip"
except ImportError:
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()  # Hide the window
        CLIPBOARD_AVAILABLE = True
        _clipboard_impl = "tkinter"
    except ImportError:
        pass

class ClipboardRequest(BaseModel):
    action: str  # "get", "set", "clear"
    content_type: Optional[str] = "text"  # "text", "image", "file", "html"
    data: Optional[Union[str, Dict[str, Any]]] = None
    encoding: Optional[str] = "utf-8"  # For text content
    dry_run: Optional[bool] = False

class DataTransferRequest(BaseModel):
    action: str  # "send", "receive", "list_formats"
    transfer_type: str  # "clipboard", "drag_drop", "file_share"
    source: Optional[Dict[str, Any]] = None
    target: Optional[Dict[str, Any]] = None
    data_format: Optional[str] = "auto"  # "text", "image", "file", "json", "auto"
    payload: Optional[Union[str, Dict[str, Any]]] = None
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

def _get_clipboard_text() -> str:
    """Get text from clipboard using available implementation"""
    if not CLIPBOARD_AVAILABLE:
        raise Exception("No clipboard implementation available")
    
    if _clipboard_impl == "pyperclip":
        return pyperclip.paste()
    elif _clipboard_impl == "tkinter":
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            return root.clipboard_get()
        finally:
            root.destroy()
    else:
        raise Exception("No valid clipboard implementation")

def _set_clipboard_text(text: str):
    """Set text to clipboard using available implementation"""
    if not CLIPBOARD_AVAILABLE:
        raise Exception("No clipboard implementation available")
    
    if _clipboard_impl == "pyperclip":
        pyperclip.copy(text)
    elif _clipboard_impl == "tkinter":
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()  # Keep clipboard after destroy
        finally:
            root.destroy()
    else:
        raise Exception("No valid clipboard implementation")

def _clear_clipboard():
    """Clear clipboard contents"""
    if not CLIPBOARD_AVAILABLE:
        raise Exception("No clipboard implementation available")
    
    if _clipboard_impl == "pyperclip":
        pyperclip.copy("")
    elif _clipboard_impl == "tkinter":
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            root.clipboard_clear()
            root.update()
        finally:
            root.destroy()

def _detect_content_type(data: Any) -> str:
    """Auto-detect content type from data"""
    if isinstance(data, str):
        if data.startswith("data:image/"):
            return "image"
        elif data.startswith("file://") or os.path.exists(data):
            return "file"
        elif data.startswith("<") and data.endswith(">"):
            return "html"
        else:
            return "text"
    elif isinstance(data, dict):
        return "json"
    elif isinstance(data, bytes):
        # Try to detect image format
        if data.startswith(b'\x89PNG'):
            return "image"
        elif data.startswith(b'\xff\xd8\xff'):
            return "image"
        else:
            return "binary"
    else:
        return "unknown"

def _encode_data(data: Any, data_format: str) -> str:
    """Encode data for transfer"""
    if data_format == "text":
        return str(data)
    elif data_format == "json":
        return json.dumps(data, indent=2)
    elif data_format == "base64":
        if isinstance(data, str):
            return base64.b64encode(data.encode()).decode()
        elif isinstance(data, bytes):
            return base64.b64encode(data).decode()
    elif data_format == "image":
        # For image data, assume it's already base64 encoded
        return str(data)
    else:
        return str(data)

def _decode_data(data: str, data_format: str) -> Any:
    """Decode data from transfer format"""
    if data_format == "json":
        return json.loads(data)
    elif data_format == "base64":
        return base64.b64decode(data)
    else:
        return data

@router.post("/", dependencies=[Depends(verify_key)])
def clipboard_operation(req: ClipboardRequest, response: Response):
    """
    Perform clipboard operations for text, images, and files.
    Supports get, set, and clear operations across content types.
    """
    start_time = time.time()
    
    if req.action not in ["get", "set", "clear"]:
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    # Safety check
    safety_result = safety_check("/clipboard", req.action, req.dict(), req.dry_run)
    if not safety_result["safe"]:
        return _error_response("SAFETY_VIOLATION", safety_result["message"], {"safety": safety_result})
    
    result = {
        "action": req.action,
        "content_type": req.content_type,
        "encoding": req.encoding,
        "dry_run": req.dry_run,
        "safety_check": safety_result,
        "clipboard_available": CLIPBOARD_AVAILABLE,
        "implementation": _clipboard_impl
    }
    
    if req.dry_run:
        result["status"] = f"would_{req.action}"
        if req.action == "get":
            result["would_retrieve"] = req.content_type
        elif req.action == "set":
            result["would_set"] = {
                "content_type": req.content_type,
                "data_length": len(str(req.data)) if req.data else 0
            }
        
        log_action("/clipboard", req.action, req.dict(), result, dry_run=True)
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
    
    if not CLIPBOARD_AVAILABLE:
        return _error_response("CLIPBOARD_UNAVAILABLE", "No clipboard implementation available")
    
    try:
        if req.action == "get":
            if req.content_type == "text":
                clipboard_text = _get_clipboard_text()
                result.update({
                    "data": clipboard_text,
                    "length": len(clipboard_text),
                    "status": "retrieved"
                })
            else:
                # For non-text types, we'd need platform-specific implementations
                result.update({
                    "data": None,
                    "status": "not_implemented",
                    "message": f"Content type '{req.content_type}' not yet implemented"
                })
        
        elif req.action == "set":
            if not req.data:
                return _error_response("MISSING_DATA", "data field required for set operation")
            
            if req.content_type == "text":
                text_data = str(req.data)
                _set_clipboard_text(text_data)
                result.update({
                    "data_set": len(text_data),
                    "status": "set"
                })
            else:
                # For non-text types, convert to text representation
                text_repr = _encode_data(req.data, req.content_type)
                _set_clipboard_text(text_repr)
                result.update({
                    "data_set": len(text_repr),
                    "status": "set_as_text",
                    "original_type": req.content_type
                })
        
        elif req.action == "clear":
            _clear_clipboard()
            result.update({
                "status": "cleared"
            })
        
        log_action("/clipboard", req.action, req.dict(), result, dry_run=False)
        
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return _error_response("CLIPBOARD_ERROR", str(e))

@router.post("/transfer", dependencies=[Depends(verify_key)])
def data_transfer(req: DataTransferRequest, response: Response):
    """
    Transfer structured data between applications and contexts.
    Supports clipboard, drag-drop, and file sharing mechanisms.
    """
    start_time = time.time()
    
    if req.action not in ["send", "receive", "list_formats"]:
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    # Safety check
    safety_result = safety_check("/clipboard", req.action, req.dict(), req.dry_run)
    if not safety_result["safe"]:
        return _error_response("SAFETY_VIOLATION", safety_result["message"], {"safety": safety_result})
    
    valid_transfer_types = ["clipboard", "drag_drop", "file_share"]
    if req.transfer_type not in valid_transfer_types:
        return _error_response("INVALID_TRANSFER_TYPE", f"transfer_type must be one of: {valid_transfer_types}")
    
    result = {
        "action": req.action,
        "transfer_type": req.transfer_type,
        "data_format": req.data_format,
        "dry_run": req.dry_run,
        "safety_check": safety_result
    }
    
    if req.dry_run:
        result["status"] = f"would_{req.action}"
        if req.action == "send" and req.payload:
            detected_format = _detect_content_type(req.payload)
            result["would_send"] = {
                "detected_format": detected_format,
                "payload_size": len(str(req.payload)),
                "transfer_type": req.transfer_type
            }
        
        log_action("/clipboard", req.action, req.dict(), result, dry_run=True)
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
    
    try:
        if req.action == "list_formats":
            # List supported data formats
            supported_formats = {
                "clipboard": ["text", "html", "json"],
                "drag_drop": ["text", "file", "image"],  # Limited implementation
                "file_share": ["text", "json", "binary", "image"]
            }
            
            result.update({
                "supported_formats": supported_formats,
                "current_capabilities": {
                    "clipboard": CLIPBOARD_AVAILABLE,
                    "drag_drop": False,  # Would need platform-specific implementation
                    "file_share": True
                },
                "status": "listed"
            })
        
        elif req.action == "send":
            if not req.payload:
                return _error_response("MISSING_PAYLOAD", "payload field required for send operation")
            
            # Auto-detect format if needed
            if req.data_format == "auto":
                req.data_format = _detect_content_type(req.payload)
            
            if req.transfer_type == "clipboard":
                # Send via clipboard
                encoded_data = _encode_data(req.payload, req.data_format)
                if CLIPBOARD_AVAILABLE:
                    _set_clipboard_text(encoded_data)
                    result.update({
                        "status": "sent_to_clipboard",
                        "format": req.data_format,
                        "size": len(encoded_data)
                    })
                else:
                    return _error_response("CLIPBOARD_UNAVAILABLE", "Clipboard not available")
            
            elif req.transfer_type == "file_share":
                # Save to temporary file
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=f'.{req.data_format}') as f:
                    if req.data_format == "json":
                        json.dump(req.payload, f, indent=2)
                    else:
                        f.write(str(req.payload))
                    temp_file = f.name
                
                result.update({
                    "status": "saved_to_file",
                    "file_path": temp_file,
                    "format": req.data_format,
                    "size": os.path.getsize(temp_file)
                })
            
            else:
                result.update({
                    "status": "not_implemented",
                    "message": f"Transfer type '{req.transfer_type}' not yet implemented"
                })
        
        elif req.action == "receive":
            if req.transfer_type == "clipboard":
                if CLIPBOARD_AVAILABLE:
                    clipboard_data = _get_clipboard_text()
                    
                    # Try to detect and decode format
                    if req.data_format == "auto":
                        req.data_format = _detect_content_type(clipboard_data)
                    
                    decoded_data = _decode_data(clipboard_data, req.data_format)
                    
                    result.update({
                        "status": "received_from_clipboard",
                        "data": decoded_data,
                        "format": req.data_format,
                        "size": len(clipboard_data)
                    })
                else:
                    return _error_response("CLIPBOARD_UNAVAILABLE", "Clipboard not available")
            
            else:
                result.update({
                    "status": "not_implemented",
                    "message": f"Receive from '{req.transfer_type}' not yet implemented"
                })
        
        log_action("/clipboard", req.action, req.dict(), result, dry_run=False)
        
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return _error_response("TRANSFER_ERROR", str(e))

@router.get("/capabilities", dependencies=[Depends(verify_key)])
def get_clipboard_capabilities():
    """Get available clipboard and data transfer capabilities"""
    capabilities = {
        "clipboard_available": CLIPBOARD_AVAILABLE,
        "implementation": _clipboard_impl,
        "supported_content_types": ["text", "html", "json"],
        "supported_transfer_types": ["clipboard", "file_share"],
        "encoding_formats": ["utf-8", "base64", "json"],
        "auto_detection": True,
        "drag_drop_support": False,  # Would require platform-specific implementation
        "file_sharing": True,
        "max_clipboard_size": 1024 * 1024,  # 1MB typical limit
        "temporary_file_support": True
    }
    
    # Add platform-specific capabilities
    import platform
    if platform.system() == "Windows":
        capabilities["native_formats"] = ["CF_TEXT", "CF_UNICODETEXT", "CF_BITMAP"]
    elif platform.system() == "Darwin":
        capabilities["native_formats"] = ["public.utf8-plain-text", "public.png", "public.html"]
    elif platform.system() == "Linux":
        capabilities["native_formats"] = ["text/plain", "text/html", "image/png"]
    
    return {
        "result": capabilities,
        "timestamp": int(time.time() * 1000)
    }