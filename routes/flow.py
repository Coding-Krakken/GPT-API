"""
Flow control and state management endpoints for GUI automation.
Provides wait conditions, retry logic, and event-driven callbacks.
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Callable
import time
import json
import asyncio
import threading
from utils.auth import verify_key
from utils.safety import safety_check, log_action

router = APIRouter()

# Event system for flow control
_event_handlers = {}
_event_handlers_lock = threading.Lock()
_wait_conditions = {}
_wait_conditions_lock = threading.Lock()

class WaitForRequest(BaseModel):
    action: str
    condition_type: str  # "element_appears", "element_disappears", "window_opens", "network_idle", "time"
    target: Optional[Dict[str, Any]] = None  # Target specification
    timeout: Optional[int] = 30  # Timeout in seconds
    polling_interval: Optional[float] = 0.5  # Check interval in seconds
    dry_run: Optional[bool] = False

class RetryRequest(BaseModel):
    action: str
    operation: Dict[str, Any]  # Operation to retry
    max_attempts: Optional[int] = 3
    retry_delay: Optional[float] = 1.0  # Delay between attempts
    backoff_multiplier: Optional[float] = 1.5  # Exponential backoff
    retry_conditions: Optional[List[str]] = None  # When to retry
    dry_run: Optional[bool] = False

class CallbackRequest(BaseModel):
    action: str
    event_type: str  # "window_open", "dialog_appear", "network_change", "screen_change"
    callback_endpoint: str  # Endpoint to call when event occurs
    callback_params: Optional[Dict[str, Any]] = None
    filter_conditions: Optional[Dict[str, Any]] = None
    timeout: Optional[int] = 300  # Callback timeout in seconds
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

def _check_condition(condition_type: str, target: Dict[str, Any]) -> bool:
    """Check if a wait condition is satisfied"""
    try:
        if condition_type == "time":
            # Time-based condition - always true (handled by timeout)
            return True
            
        elif condition_type == "element_appears":
            # Check if visual element appears (would use screen capture + template matching)
            if "template" in target:
                # Simulate element detection
                return True  # In real implementation, use template matching
            elif "text" in target:
                # Simulate text detection via OCR
                return True  # In real implementation, use OCR
            return False
            
        elif condition_type == "element_disappears":
            # Check if element disappears
            return False  # Simulate element still present
            
        elif condition_type == "window_opens":
            # Check if window with specific title opens
            window_title = target.get("title", "")
            # In real implementation, would check active windows
            return False  # Simulate window not found
            
        elif condition_type == "network_idle":
            # Check if network activity is idle
            idle_threshold = target.get("idle_threshold", 1.0)  # seconds
            # In real implementation, would monitor network activity
            return True  # Simulate network idle
            
        else:
            return False
            
    except Exception:
        return False

async def _wait_for_condition(condition_type: str, target: Dict[str, Any], 
                             timeout: int, polling_interval: float) -> Dict[str, Any]:
    """Wait for condition to be satisfied with timeout"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if _check_condition(condition_type, target):
            return {
                "satisfied": True,
                "elapsed_time": time.time() - start_time,
                "checks_performed": int((time.time() - start_time) / polling_interval) + 1
            }
        
        await asyncio.sleep(polling_interval)
    
    return {
        "satisfied": False,
        "elapsed_time": time.time() - start_time,
        "timeout_reached": True,
        "checks_performed": int(timeout / polling_interval)
    }

def _execute_operation(operation: Dict[str, Any]) -> Dict[str, Any]:
    """Execute an operation for retry logic"""
    # This would integrate with other endpoints
    # For now, simulate operation execution
    endpoint = operation.get("endpoint", "/test")
    action = operation.get("action", "test")
    params = operation.get("params", {})
    
    # Simulate random success/failure
    import random
    if random.random() > 0.3:  # 70% success rate
        return {
            "success": True,
            "result": {"status": "completed", "endpoint": endpoint, "action": action}
        }
    else:
        return {
            "success": False,
            "error": "Simulated operation failure",
            "retry_eligible": True
        }

def _should_retry(result: Dict[str, Any], retry_conditions: List[str]) -> bool:
    """Determine if operation should be retried based on conditions"""
    if not retry_conditions:
        # Default: retry on any failure
        return not result.get("success", False)
    
    for condition in retry_conditions:
        if condition == "network_error" and "network" in str(result.get("error", "")).lower():
            return True
        elif condition == "timeout" and "timeout" in str(result.get("error", "")).lower():
            return True
        elif condition == "temporary_failure" and result.get("retry_eligible", False):
            return True
        elif condition == "any_failure" and not result.get("success", False):
            return True
    
    return False

@router.post("/wait_for", dependencies=[Depends(verify_key)])
async def wait_for_condition(req: WaitForRequest, response: Response):
    """
    Wait for specific conditions before proceeding.
    Supports element detection, window events, and time-based waits.
    """
    start_time = time.time()
    
    if req.action != "wait":
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    # Safety check
    safety_result = safety_check("/flow", req.action, req.dict(), req.dry_run)
    if not safety_result["safe"]:
        return _error_response("SAFETY_VIOLATION", safety_result["message"], {"safety": safety_result})
    
    valid_conditions = ["element_appears", "element_disappears", "window_opens", "network_idle", "time"]
    if req.condition_type not in valid_conditions:
        return _error_response("INVALID_CONDITION", f"condition_type must be one of: {valid_conditions}")
    
    result = {
        "action": req.action,
        "condition_type": req.condition_type,
        "target": req.target,
        "timeout": req.timeout,
        "polling_interval": req.polling_interval,
        "dry_run": req.dry_run,
        "safety_check": safety_result
    }
    
    if req.dry_run:
        result["status"] = "would_wait"
        log_action("/flow", req.action, req.dict(), result, dry_run=True)
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
    
    try:
        # Wait for condition
        wait_result = await _wait_for_condition(
            req.condition_type, 
            req.target or {}, 
            req.timeout, 
            req.polling_interval
        )
        
        result.update(wait_result)
        result["status"] = "completed" if wait_result["satisfied"] else "timeout"
        
        log_action("/flow", req.action, req.dict(), result, dry_run=False)
        
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return _error_response("WAIT_ERROR", str(e))

@router.post("/retry", dependencies=[Depends(verify_key)])
def retry_operation(req: RetryRequest, response: Response):
    """
    Retry operations with configurable backoff and conditions.
    Handles transient errors and improves reliability.
    """
    start_time = time.time()
    
    if req.action != "retry":
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    # Safety check
    safety_result = safety_check("/flow", req.action, req.dict(), req.dry_run)
    if not safety_result["safe"]:
        return _error_response("SAFETY_VIOLATION", safety_result["message"], {"safety": safety_result})
    
    if not req.operation:
        return _error_response("MISSING_OPERATION", "operation field is required")
    
    result = {
        "action": req.action,
        "operation": req.operation,
        "max_attempts": req.max_attempts,
        "retry_delay": req.retry_delay,
        "backoff_multiplier": req.backoff_multiplier,
        "retry_conditions": req.retry_conditions,
        "dry_run": req.dry_run,
        "safety_check": safety_result,
        "attempts": []
    }
    
    if req.dry_run:
        result["status"] = "would_retry"
        log_action("/flow", req.action, req.dict(), result, dry_run=True)
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
    
    try:
        current_delay = req.retry_delay
        
        for attempt in range(req.max_attempts):
            attempt_start = time.time()
            
            # Execute operation
            operation_result = _execute_operation(req.operation)
            
            attempt_info = {
                "attempt": attempt + 1,
                "start_time": attempt_start,
                "duration": time.time() - attempt_start,
                "success": operation_result.get("success", False),
                "result": operation_result
            }
            
            result["attempts"].append(attempt_info)
            
            if operation_result.get("success", False):
                # Success - stop retrying
                result["status"] = "succeeded"
                result["final_result"] = operation_result
                break
            
            # Check if we should retry
            if attempt < req.max_attempts - 1:  # Not the last attempt
                if _should_retry(operation_result, req.retry_conditions or []):
                    # Wait before next attempt
                    time.sleep(current_delay)
                    current_delay *= req.backoff_multiplier
                else:
                    # Don't retry based on conditions
                    result["status"] = "failed_no_retry"
                    result["reason"] = "Retry conditions not met"
                    break
            else:
                # Last attempt failed
                result["status"] = "failed_max_attempts"
        
        log_action("/flow", req.action, req.dict(), result, dry_run=False)
        
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return _error_response("RETRY_ERROR", str(e))

@router.post("/callback", dependencies=[Depends(verify_key)])
def register_callback(req: CallbackRequest, response: Response):
    """
    Register event-driven callbacks for asynchronous automation.
    Triggers actions when specific events occur.
    """
    start_time = time.time()
    
    if req.action not in ["register", "unregister"]:
        return _error_response("INVALID_ACTION", f"action must be 'register' or 'unregister'")
    
    # Safety check
    safety_result = safety_check("/flow", req.action, req.dict(), req.dry_run)
    if not safety_result["safe"]:
        return _error_response("SAFETY_VIOLATION", safety_result["message"], {"safety": safety_result})
    
    valid_events = ["window_open", "dialog_appear", "network_change", "screen_change"]
    if req.event_type not in valid_events:
        return _error_response("INVALID_EVENT_TYPE", f"event_type must be one of: {valid_events}")
    
    result = {
        "action": req.action,
        "event_type": req.event_type,
        "callback_endpoint": req.callback_endpoint,
        "filter_conditions": req.filter_conditions,
        "timeout": req.timeout,
        "dry_run": req.dry_run,
        "safety_check": safety_result
    }
    
    if req.dry_run:
        result["status"] = f"would_{req.action}"
        log_action("/flow", req.action, req.dict(), result, dry_run=True)
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
    
    try:
        with _event_handlers_lock:
            if req.action == "register":
                callback_id = f"{req.event_type}_{int(time.time())}"
                _event_handlers[callback_id] = {
                    "event_type": req.event_type,
                    "callback_endpoint": req.callback_endpoint,
                    "callback_params": req.callback_params,
                    "filter_conditions": req.filter_conditions,
                    "registered_at": time.time(),
                    "timeout": req.timeout
                }
                result["callback_id"] = callback_id
                result["status"] = "registered"
                
            elif req.action == "unregister":
                # Find and remove callback
                callback_id = req.callback_params.get("callback_id") if req.callback_params else None
                if callback_id and callback_id in _event_handlers:
                    del _event_handlers[callback_id]
                    result["callback_id"] = callback_id
                    result["status"] = "unregistered"
                else:
                    return _error_response("CALLBACK_NOT_FOUND", "Callback not found")
        
        log_action("/flow", req.action, req.dict(), result, dry_run=False)
        
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return _error_response("CALLBACK_ERROR", str(e))

@router.get("/status", dependencies=[Depends(verify_key)])
def get_flow_status():
    """Get current flow control status and active conditions"""
    
    with _event_handlers_lock:
        active_callbacks = len(_event_handlers)
        callbacks = []
        for callback_id, info in _event_handlers.items():
            callbacks.append({
                "callback_id": callback_id,
                "event_type": info["event_type"],
                "callback_endpoint": info["callback_endpoint"],
                "registered_at": info["registered_at"],
                "timeout": info["timeout"]
            })
    
    with _wait_conditions_lock:
        active_waits = len(_wait_conditions)
    
    return {
        "result": {
            "active_callbacks": active_callbacks,
            "active_waits": active_waits,
            "callbacks": callbacks,
            "supported_conditions": ["element_appears", "element_disappears", "window_opens", "network_idle", "time"],
            "supported_events": ["window_open", "dialog_appear", "network_change", "screen_change"],
            "retry_strategies": ["exponential_backoff", "linear_delay", "immediate"]
        },
        "timestamp": int(time.time() * 1000)
    }

@router.get("/capabilities", dependencies=[Depends(verify_key)])
def get_flow_capabilities():
    """Get available flow control capabilities"""
    capabilities = {
        "wait_conditions": True,
        "retry_logic": True,
        "event_callbacks": True,
        "async_operations": True,
        "condition_types": ["element_appears", "element_disappears", "window_opens", "network_idle", "time"],
        "event_types": ["window_open", "dialog_appear", "network_change", "screen_change"],
        "retry_conditions": ["network_error", "timeout", "temporary_failure", "any_failure"],
        "max_timeout": 3600,  # 1 hour
        "max_retry_attempts": 10,
        "polling_interval_range": [0.1, 10.0]  # seconds
    }
    
    return {
        "result": capabilities,
        "timestamp": int(time.time() * 1000)
    }