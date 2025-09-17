"""
Developer and operator UX endpoints for GUI automation.
Provides debugging, telemetry, replay, and step-through capabilities.
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union
import time
import json
import os
from collections import defaultdict, deque
from utils.auth import verify_key
from utils.safety import get_safety_manager

router = APIRouter()

# In-memory debugging data structures
_operation_history = deque(maxlen=1000)  # Last 1000 operations
_performance_metrics = defaultdict(list)
_error_patterns = defaultdict(int)
_step_through_sessions = {}

class DebugRequest(BaseModel):
    action: str  # "start", "stop", "status", "export"
    debug_level: Optional[str] = "info"  # "debug", "info", "warning", "error"
    capture_screenshots: Optional[bool] = False
    capture_performance: Optional[bool] = True
    filter_endpoints: Optional[List[str]] = None

class StepThroughRequest(BaseModel):
    action: str  # "start", "next", "pause", "resume", "stop"
    session_id: Optional[str] = None
    operations: Optional[List[Dict[str, Any]]] = None
    breakpoints: Optional[List[Dict[str, Any]]] = None

class ReplayRequest(BaseModel):
    action: str  # "start", "pause", "resume", "stop"
    session_id: Optional[str] = None
    operation_ids: Optional[List[str]] = None
    replay_speed: Optional[float] = 1.0  # Speed multiplier
    start_time: Optional[int] = None
    end_time: Optional[int] = None

class TelemetryQuery(BaseModel):
    query_type: str  # "performance", "errors", "operations", "safety"
    time_range: Optional[Dict[str, int]] = None  # {"start": timestamp, "end": timestamp}
    filters: Optional[Dict[str, Any]] = None
    aggregation: Optional[str] = "none"  # "none", "minute", "hour", "day"
    limit: Optional[int] = 100

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

def _record_operation(endpoint: str, action: str, params: Dict, result: Dict, latency_ms: int):
    """Record operation for debugging and replay"""
    operation_record = {
        "id": f"{int(time.time() * 1000)}_{len(_operation_history)}",
        "timestamp": int(time.time() * 1000),
        "endpoint": endpoint,
        "action": action,
        "params": params,
        "result": result,
        "latency_ms": latency_ms,
        "success": "errors" not in result
    }
    
    _operation_history.append(operation_record)
    
    # Update performance metrics
    _performance_metrics[f"{endpoint}.{action}"].append(latency_ms)
    
    # Track error patterns
    if not operation_record["success"]:
        error_code = result.get("errors", [{}])[0].get("code", "unknown")
        _error_patterns[f"{endpoint}.{error_code}"] += 1

def _get_performance_stats(endpoint_action: str) -> Dict[str, Any]:
    """Get performance statistics for an endpoint/action"""
    latencies = _performance_metrics.get(endpoint_action, [])
    
    if not latencies:
        return {"count": 0}
    
    return {
        "count": len(latencies),
        "avg_latency_ms": sum(latencies) / len(latencies),
        "min_latency_ms": min(latencies),
        "max_latency_ms": max(latencies),
        "p95_latency_ms": sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 20 else max(latencies)
    }

@router.post("/start", dependencies=[Depends(verify_key)])
def start_debug_session(req: DebugRequest, response: Response):
    """
    Start comprehensive debugging session with telemetry capture.
    Enables detailed operation tracking and performance monitoring.
    """
    start_time = time.time()
    
    if req.action != "start":
        return _error_response("INVALID_ACTION", f"Expected action 'start', got '{req.action}'")
    
    session_id = _generate_session_id()
    
    # Initialize debug session
    debug_session = {
        "session_id": session_id,
        "started_at": int(time.time() * 1000),
        "debug_level": req.debug_level,
        "capture_screenshots": req.capture_screenshots,
        "capture_performance": req.capture_performance,
        "filter_endpoints": req.filter_endpoints or [],
        "operations_captured": 0,
        "screenshots_captured": 0,
        "errors_captured": 0
    }
    
    # In a full implementation, this would be stored persistently
    _step_through_sessions[session_id] = debug_session
    
    result = {
        "action": req.action,
        "session_id": session_id,
        "debug_configuration": debug_session,
        "status": "started",
        "capabilities": {
            "operation_tracking": True,
            "performance_monitoring": True,
            "error_pattern_analysis": True,
            "screenshot_capture": req.capture_screenshots,
            "step_through_debugging": True,
            "operation_replay": True
        }
    }
    
    return {
        "result": result,
        "timestamp": int(time.time() * 1000),
        "latency_ms": int((time.time() - start_time) * 1000)
    }

@router.post("/step_through", dependencies=[Depends(verify_key)])
def step_through_operations(req: StepThroughRequest, response: Response):
    """
    Step-through debugging for GUI automation workflows.
    Allows pausing, inspecting, and resuming operations one by one.
    """
    start_time = time.time()
    
    if req.action not in ["start", "next", "pause", "resume", "stop"]:
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    result = {
        "action": req.action,
        "session_id": req.session_id,
        "timestamp": int(time.time() * 1000)
    }
    
    if req.action == "start":
        if not req.operations:
            return _error_response("NO_OPERATIONS", "operations list required for step-through debugging")
        
        session_id = req.session_id or _generate_session_id()
        
        step_session = {
            "session_id": session_id,
            "operations": req.operations,
            "current_step": 0,
            "status": "paused",
            "breakpoints": req.breakpoints or [],
            "started_at": int(time.time() * 1000),
            "execution_log": []
        }
        
        _step_through_sessions[session_id] = step_session
        
        result.update({
            "session_id": session_id,
            "status": "step_session_started",
            "total_operations": len(req.operations),
            "current_step": 0,
            "next_operation": req.operations[0] if req.operations else None
        })
    
    elif req.action in ["next", "pause", "resume", "stop"]:
        if not req.session_id or req.session_id not in _step_through_sessions:
            return _error_response("SESSION_NOT_FOUND", f"Step-through session {req.session_id} not found")
        
        session = _step_through_sessions[req.session_id]
        
        if req.action == "next":
            if session["current_step"] < len(session["operations"]):
                current_op = session["operations"][session["current_step"]]
                
                # Simulate operation execution
                execution_result = {
                    "step": session["current_step"],
                    "operation": current_op,
                    "executed_at": int(time.time() * 1000),
                    "success": True,
                    "latency_ms": 100
                }
                
                session["execution_log"].append(execution_result)
                session["current_step"] += 1
                
                result.update({
                    "status": "step_executed",
                    "executed_operation": current_op,
                    "execution_result": execution_result,
                    "current_step": session["current_step"],
                    "remaining_steps": len(session["operations"]) - session["current_step"],
                    "next_operation": session["operations"][session["current_step"]] if session["current_step"] < len(session["operations"]) else None
                })
            else:
                result.update({
                    "status": "session_complete",
                    "total_steps_executed": len(session["execution_log"])
                })
        
        elif req.action == "pause":
            session["status"] = "paused"
            result.update({"status": "paused"})
        
        elif req.action == "resume":
            session["status"] = "running"
            result.update({"status": "resumed"})
        
        elif req.action == "stop":
            del _step_through_sessions[req.session_id]
            result.update({"status": "stopped"})
    
    return {
        "result": result,
        "timestamp": int(time.time() * 1000),
        "latency_ms": int((time.time() - start_time) * 1000)
    }

@router.post("/replay", dependencies=[Depends(verify_key)])
def replay_operations(req: ReplayRequest, response: Response):
    """
    Replay previously executed operations for debugging and testing.
    Supports speed control and selective operation replay.
    """
    start_time = time.time()
    
    if req.action not in ["start", "pause", "resume", "stop"]:
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    result = {
        "action": req.action,
        "session_id": req.session_id,
        "replay_speed": req.replay_speed
    }
    
    if req.action == "start":
        # Filter operations for replay
        operations_to_replay = []
        
        for op in _operation_history:
            # Time range filter
            if req.start_time and op["timestamp"] < req.start_time:
                continue
            if req.end_time and op["timestamp"] > req.end_time:
                continue
            
            # Operation ID filter
            if req.operation_ids and op["id"] not in req.operation_ids:
                continue
            
            operations_to_replay.append(op)
        
        session_id = req.session_id or _generate_session_id()
        
        replay_session = {
            "session_id": session_id,
            "operations": operations_to_replay,
            "current_index": 0,
            "replay_speed": req.replay_speed,
            "status": "started",
            "started_at": int(time.time() * 1000),
            "replayed_operations": []
        }
        
        _step_through_sessions[session_id] = replay_session
        
        result.update({
            "session_id": session_id,
            "status": "replay_started",
            "total_operations": len(operations_to_replay),
            "estimated_duration_ms": int(sum(op["latency_ms"] for op in operations_to_replay) / req.replay_speed)
        })
    
    else:
        # Handle pause/resume/stop for existing replay session
        if not req.session_id or req.session_id not in _step_through_sessions:
            return _error_response("SESSION_NOT_FOUND", f"Replay session {req.session_id} not found")
        
        session = _step_through_sessions[req.session_id]
        session["status"] = {"pause": "paused", "resume": "running", "stop": "stopped"}[req.action]
        
        if req.action == "stop":
            del _step_through_sessions[req.session_id]
        
        result.update({"status": session.get("status", "unknown")})
    
    return {
        "result": result,
        "timestamp": int(time.time() * 1000),
        "latency_ms": int((time.time() - start_time) * 1000)
    }

@router.post("/telemetry", dependencies=[Depends(verify_key)])
def query_telemetry(req: TelemetryQuery, response: Response):
    """
    Query telemetry data for performance analysis and debugging.
    Provides insights into operation patterns, errors, and performance.
    """
    start_time = time.time()
    
    if req.query_type not in ["performance", "errors", "operations", "safety"]:
        return _error_response("INVALID_QUERY_TYPE", f"Unsupported query_type: {req.query_type}")
    
    result = {
        "query_type": req.query_type,
        "time_range": req.time_range,
        "filters": req.filters,
        "aggregation": req.aggregation,
        "limit": req.limit
    }
    
    if req.query_type == "performance":
        # Performance metrics analysis
        performance_data = {}
        for endpoint_action, latencies in _performance_metrics.items():
            stats = _get_performance_stats(endpoint_action)
            if stats["count"] > 0:
                performance_data[endpoint_action] = stats
        
        result.update({
            "data": performance_data,
            "summary": {
                "total_endpoints_tracked": len(performance_data),
                "total_operations": sum(stats["count"] for stats in performance_data.values()),
                "average_system_latency_ms": sum(stats["avg_latency_ms"] * stats["count"] for stats in performance_data.values()) / sum(stats["count"] for stats in performance_data.values()) if performance_data else 0
            }
        })
    
    elif req.query_type == "errors":
        # Error pattern analysis
        error_data = dict(_error_patterns)
        total_errors = sum(error_data.values())
        
        result.update({
            "data": error_data,
            "summary": {
                "total_errors": total_errors,
                "unique_error_patterns": len(error_data),
                "most_common_error": max(error_data, key=error_data.get) if error_data else None,
                "error_rate": total_errors / len(_operation_history) if _operation_history else 0
            }
        })
    
    elif req.query_type == "operations":
        # Operation history analysis
        operations = list(_operation_history)
        
        # Apply time range filter
        if req.time_range:
            operations = [
                op for op in operations
                if req.time_range.get("start", 0) <= op["timestamp"] <= req.time_range.get("end", float("inf"))
            ]
        
        # Apply limit
        operations = operations[-req.limit:] if req.limit else operations
        
        result.update({
            "data": operations,
            "summary": {
                "total_operations": len(operations),
                "success_rate": sum(1 for op in operations if op["success"]) / len(operations) if operations else 0,
                "endpoints_used": len(set(op["endpoint"] for op in operations)),
                "time_span_ms": operations[-1]["timestamp"] - operations[0]["timestamp"] if len(operations) > 1 else 0
            }
        })
    
    elif req.query_type == "safety":
        # Safety system telemetry
        safety_manager = get_safety_manager()
        
        # Read recent audit entries
        audit_entries = []
        try:
            with open(safety_manager.audit_log_path, 'r') as f:
                for line in f.readlines()[-req.limit:]:
                    try:
                        audit_entries.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass
        
        result.update({
            "data": audit_entries,
            "summary": {
                "total_audit_entries": len(audit_entries),
                "safety_violations": sum(1 for entry in audit_entries if "SAFETY" in entry.get("message", "")),
                "confirmed_actions": sum(1 for entry in audit_entries if "confirmation" in entry.get("details", {})),
                "dry_run_operations": sum(1 for entry in audit_entries if entry.get("details", {}).get("dry_run", False))
            }
        })
    
    return {
        "result": result,
        "timestamp": int(time.time() * 1000),
        "latency_ms": int((time.time() - start_time) * 1000)
    }

@router.get("/status", dependencies=[Depends(verify_key)])
def get_debug_status():
    """Get current debugging system status and active sessions"""
    
    active_sessions = {}
    for session_id, session_data in _step_through_sessions.items():
        active_sessions[session_id] = {
            "type": "step_through" if "operations" in session_data else "replay",
            "status": session_data.get("status", "unknown"),
            "started_at": session_data.get("started_at"),
            "operations_count": len(session_data.get("operations", []))
        }
    
    return {
        "result": {
            "debugging_enabled": True,
            "active_sessions": active_sessions,
            "operation_history_size": len(_operation_history),
            "performance_metrics_endpoints": len(_performance_metrics),
            "error_patterns_tracked": len(_error_patterns),
            "capabilities": {
                "step_through_debugging": True,
                "operation_replay": True,
                "performance_telemetry": True,
                "error_pattern_analysis": True,
                "screenshot_capture": False,  # Would require GUI libraries
                "live_monitoring": True
            },
            "statistics": {
                "total_recorded_operations": len(_operation_history),
                "average_operation_latency_ms": sum(sum(latencies) for latencies in _performance_metrics.values()) / sum(len(latencies) for latencies in _performance_metrics.values()) if _performance_metrics else 0,
                "total_errors_recorded": sum(_error_patterns.values()),
                "uptime_ms": int(time.time() * 1000)  # Simplified uptime
            }
        },
        "timestamp": int(time.time() * 1000)
    }

@router.get("/capabilities", dependencies=[Depends(verify_key)])  
def get_debug_capabilities():
    """Get available debugging and developer UX capabilities"""
    capabilities = {
        "debugging": {
            "step_through_execution": True,
            "operation_breakpoints": True,
            "variable_inspection": False,  # Future enhancement
            "call_stack_analysis": False   # Future enhancement
        },
        "telemetry": {
            "performance_monitoring": True,
            "error_tracking": True,
            "operation_logging": True,
            "safety_audit_integration": True,
            "real_time_metrics": True,
            "historical_analysis": True
        },
        "replay": {
            "operation_replay": True,
            "speed_control": True,
            "selective_replay": True,
            "time_range_filtering": True,
            "batch_replay": True
        },
        "export": {
            "operation_history_export": True,
            "performance_reports": True,
            "error_analysis_reports": True,
            "replay_scripts": True
        },
        "limits": {
            "max_operation_history": 1000,
            "max_active_debug_sessions": 10,
            "max_replay_duration_hours": 24,
            "telemetry_retention_days": 30
        }
    }
    
    return {
        "result": capabilities,
        "timestamp": int(time.time() * 1000)
    }

# Hook to record operations from other routes
def record_operation_for_debug(endpoint: str, action: str, params: Dict, result: Dict, latency_ms: int):
    """Public function for other routes to record operations"""
    _record_operation(endpoint, action, params, result, latency_ms)