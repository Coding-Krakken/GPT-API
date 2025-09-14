"""
Enhanced safety and governance endpoints for GUI automation.
Provides confirmation flows, audit logging, step-through modes, and comprehensive governance.
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import time
import json
import os
from utils.auth import verify_key
from utils.safety import (
    get_safety_manager, safety_check, SafetyLevel, ActionType, ConfirmationMode,
    create_confirmation, confirm_action, list_pending_actions
)

router = APIRouter()

class SafetyCheckRequest(BaseModel):
    endpoint: str
    action: str
    params: Dict[str, Any]
    dry_run: Optional[bool] = False
    confirmed: Optional[bool] = False
    confirmation_token: Optional[str] = None

class ConfirmationRequest(BaseModel):
    action_id: str
    confirmed: bool
    confirmation_token: Optional[str] = None
    reason: Optional[str] = None

class StepThroughRequest(BaseModel):
    session_id: str
    action: str  # next, pause, resume, stop, add_breakpoint
    step_number: Optional[int] = None
    variable_name: Optional[str] = None
    variable_value: Optional[Any] = None

class AuditQueryRequest(BaseModel):
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    level: Optional[str] = None
    endpoint: Optional[str] = None
    action_type: Optional[str] = None
    include_destructive_only: Optional[bool] = False
    limit: Optional[int] = 100

class TelemetryQueryRequest(BaseModel):
    event_type: Optional[str] = None
    hours: Optional[int] = 24
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

@router.post("/check", dependencies=[Depends(verify_key)])
def safety_check_endpoint(req: SafetyCheckRequest, response: Response):
    """
    Enhanced safety check with confirmation management and step-through support.
    Returns comprehensive safety assessment and handles confirmation workflow.
    """
    start_time = time.time()
    
    try:
        safety_result = safety_check(
            req.endpoint, 
            req.action, 
            req.params, 
            req.dry_run, 
            req.confirmed,
            req.confirmation_token
        )
        
        # Add additional context
        safety_result.update({
            "endpoint": req.endpoint,
            "action": req.action,
            "dry_run_requested": req.dry_run,
            "confirmation_provided": req.confirmed,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        })
        
        return {"result": safety_result}
        
    except Exception as e:
        return _error_response("SAFETY_CHECK_ERROR", str(e))

@router.post("/confirm", dependencies=[Depends(verify_key)])
def confirmation_endpoint(req: ConfirmationRequest, response: Response):
    """
    Enhanced confirmation handling with token validation and audit logging.
    Manages the complete confirmation workflow for pending actions.
    """
    start_time = time.time()
    
    try:
        safety_manager = get_safety_manager()
        
        # Get pending action details
        pending_action = safety_manager.confirmation_manager.get_pending_action(req.action_id)
        
        if not pending_action:
            return _error_response("ACTION_NOT_FOUND", f"No pending action found with ID: {req.action_id}")
        
        # Check if action has expired
        if time.time() > pending_action.expires_at:
            return _error_response("ACTION_EXPIRED", "Confirmation request has expired")
        
        success = False
        if req.confirmed:
            success = safety_manager.confirmation_manager.confirm_action(
                req.action_id, req.confirmation_token
            )
        else:
            # User rejected the action
            success = True  # Successfully recorded rejection
        
        if not success and req.confirmed:
            return _error_response("CONFIRMATION_FAILED", "Failed to confirm action - invalid token or expired")
        
        result = {
            "action_id": req.action_id,
            "confirmed": req.confirmed,
            "success": success,
            "reason": req.reason,
            "status": "approved" if req.confirmed and success else "rejected",
            "pending_action": {
                "endpoint": pending_action.endpoint,
                "action": pending_action.action,
                "created_at": pending_action.timestamp,
                "expires_at": pending_action.expires_at
            }
        }
        
        # Log the confirmation decision
        safety_manager._log_audit(
            "ACTION", 
            f"Confirmation {'approved' if req.confirmed else 'rejected'}: {pending_action.endpoint}.{pending_action.action}",
            {
                "action_id": req.action_id,
                "confirmed": req.confirmed,
                "reason": req.reason,
                "confirmation_token_used": bool(req.confirmation_token)
            }
        )
        
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return _error_response("CONFIRMATION_ERROR", str(e))

@router.get("/pending", dependencies=[Depends(verify_key)])
def list_pending_confirmations():
    """List all pending actions requiring confirmation"""
    
    try:
        pending_actions = list_pending_actions()
        
        # Format for API response
        formatted_actions = []
        for action in pending_actions:
            formatted_actions.append({
                "action_id": action.action_id,
                "endpoint": action.endpoint,
                "action": action.action,
                "created_at": action.timestamp,
                "expires_at": action.expires_at,
                "expires_in_seconds": max(0, int(action.expires_at - time.time())),
                "confirmation_token": action.confirmation_token,
                "safety_context": action.safety_context,
                "params_preview": str(action.params)[:200] + "..." if len(str(action.params)) > 200 else str(action.params)
            })
        
        return {
            "result": {
                "pending_actions": formatted_actions,
                "total_count": len(formatted_actions)
            },
            "timestamp": int(time.time() * 1000)
        }
        
    except Exception as e:
        return _error_response("PENDING_LIST_ERROR", str(e))

@router.post("/step_through", dependencies=[Depends(verify_key)])
def step_through_debug(req: StepThroughRequest, response: Response):
    """
    Handle step-through debugging mode for complex action sequences.
    Provides fine-grained control over action execution with breakpoints.
    """
    start_time = time.time()
    
    try:
        safety_manager = get_safety_manager()
        debugger = safety_manager.step_through_debugger
        
        if req.action == "next":
            step_result = debugger.next_step(req.session_id)
            if not step_result:
                return _error_response("SESSION_NOT_FOUND", f"No active session: {req.session_id}")
            
            return {
                "result": step_result,
                "timestamp": int(time.time() * 1000),
                "latency_ms": int((time.time() - start_time) * 1000)
            }
        
        elif req.action == "add_breakpoint":
            if req.step_number is None:
                return _error_response("MISSING_STEP_NUMBER", "Step number required for breakpoint")
            
            debugger.add_breakpoint(req.session_id, req.step_number)
            
            return {
                "result": {
                    "session_id": req.session_id,
                    "action": "breakpoint_added",
                    "step_number": req.step_number
                },
                "timestamp": int(time.time() * 1000),
                "latency_ms": int((time.time() - start_time) * 1000)
            }
        
        elif req.action == "set_variable":
            if not req.variable_name:
                return _error_response("MISSING_VARIABLE_NAME", "Variable name required")
            
            debugger.set_variable(req.session_id, req.variable_name, req.variable_value)
            
            return {
                "result": {
                    "session_id": req.session_id,
                    "action": "variable_set",
                    "variable_name": req.variable_name,
                    "variable_value": req.variable_value
                },
                "timestamp": int(time.time() * 1000),
                "latency_ms": int((time.time() - start_time) * 1000)
            }
        
        elif req.action == "get_session":
            session = debugger.get_session(req.session_id)
            if not session:
                return _error_response("SESSION_NOT_FOUND", f"No session: {req.session_id}")
            
            return {
                "result": session,
                "timestamp": int(time.time() * 1000),
                "latency_ms": int((time.time() - start_time) * 1000)
            }
        
        else:
            return _error_response("INVALID_ACTION", f"Unknown step-through action: {req.action}")
        
    except Exception as e:
        return _error_response("STEP_THROUGH_ERROR", str(e))

@router.post("/audit", dependencies=[Depends(verify_key)])
def query_audit_log(req: AuditQueryRequest, response: Response):
    """
    Enhanced audit log querying with filtering, analysis, and export capabilities.
    Provides comprehensive audit trail analysis and compliance reporting.
    """
    start_time = time.time()
    
    try:
        safety_manager = get_safety_manager()
        audit_entries = []
        
        # Read audit log file
        try:
            with open(safety_manager.audit_log_path, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        
                        # Apply filters
                        if req.start_time and entry.get("timestamp", 0) < req.start_time:
                            continue
                        if req.end_time and entry.get("timestamp", 0) > req.end_time:
                            continue
                        if req.level and entry.get("level") != req.level:
                            continue
                        if req.endpoint and req.endpoint not in entry.get("details", {}).get("endpoint", ""):
                            continue
                        if req.action_type and entry.get("details", {}).get("action_type") != req.action_type:
                            continue
                        if req.include_destructive_only and not entry.get("details", {}).get("is_destructive", False):
                            continue
                        
                        audit_entries.append(entry)
                        
                        if len(audit_entries) >= req.limit:
                            break
                            
                    except json.JSONDecodeError:
                        continue  # Skip malformed entries
                        
        except FileNotFoundError:
            # No audit log yet
            pass
        
        # Sort by timestamp (newest first)
        audit_entries.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        
        # Generate summary statistics
        summary = {
            "total_entries": len(audit_entries),
            "by_level": {},
            "by_action_type": {},
            "by_endpoint": {},
            "destructive_actions": 0,
            "time_range": {
                "start": req.start_time,
                "end": req.end_time,
                "actual_start": min([e.get("timestamp", 0) for e in audit_entries]) if audit_entries else None,
                "actual_end": max([e.get("timestamp", 0) for e in audit_entries]) if audit_entries else None
            }
        }
        
        for entry in audit_entries:
            level = entry.get("level", "UNKNOWN")
            summary["by_level"][level] = summary["by_level"].get(level, 0) + 1
            
            details = entry.get("details", {})
            if details:
                action_type = details.get("action_type")
                if action_type:
                    summary["by_action_type"][action_type] = summary["by_action_type"].get(action_type, 0) + 1
                
                endpoint = details.get("endpoint")
                if endpoint:
                    summary["by_endpoint"][endpoint] = summary["by_endpoint"].get(endpoint, 0) + 1
                
                if details.get("is_destructive"):
                    summary["destructive_actions"] += 1
        
        return {
            "result": {
                "entries": audit_entries[:req.limit],
                "summary": summary,
                "filters_applied": {
                    "start_time": req.start_time,
                    "end_time": req.end_time,
                    "level": req.level,
                    "endpoint": req.endpoint,
                    "action_type": req.action_type,
                    "destructive_only": req.include_destructive_only,
                    "limit": req.limit
                }
            },
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return _error_response("AUDIT_QUERY_ERROR", str(e))

@router.post("/telemetry", dependencies=[Depends(verify_key)])
def query_telemetry(req: TelemetryQueryRequest, response: Response):
    """
    Query telemetry data for performance and usage analysis.
    Provides insights into system performance and usage patterns.
    """
    start_time = time.time()
    
    try:
        safety_manager = get_safety_manager()
        cutoff_time = int((time.time() - (req.hours * 3600)) * 1000)
        telemetry_entries = []
        
        try:
            with open(safety_manager.telemetry_log_path, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        
                        if entry.get("timestamp", 0) < cutoff_time:
                            continue
                        
                        if req.event_type and entry.get("event_type") != req.event_type:
                            continue
                        
                        telemetry_entries.append(entry)
                        
                        if len(telemetry_entries) >= req.limit:
                            break
                    
                    except json.JSONDecodeError:
                        continue
        
        except FileNotFoundError:
            pass
        
        # Generate telemetry summary
        summary = {
            "total_events": len(telemetry_entries),
            "time_period_hours": req.hours,
            "by_event_type": {},
            "performance_metrics": {
                "avg_duration_ms": 0,
                "max_duration_ms": 0,
                "min_duration_ms": float('inf'),
                "success_rate": 0
            }
        }
        
        durations = []
        successes = 0
        
        for entry in telemetry_entries:
            event_type = entry.get("event_type", "unknown")
            summary["by_event_type"][event_type] = summary["by_event_type"].get(event_type, 0) + 1
            
            data = entry.get("data", {})
            if "duration_ms" in data:
                duration = data["duration_ms"]
                durations.append(duration)
                summary["performance_metrics"]["max_duration_ms"] = max(
                    summary["performance_metrics"]["max_duration_ms"], duration
                )
                summary["performance_metrics"]["min_duration_ms"] = min(
                    summary["performance_metrics"]["min_duration_ms"], duration
                )
            
            if data.get("success"):
                successes += 1
        
        if durations:
            summary["performance_metrics"]["avg_duration_ms"] = sum(durations) / len(durations)
        if summary["performance_metrics"]["min_duration_ms"] == float('inf'):
            summary["performance_metrics"]["min_duration_ms"] = 0
        
        if telemetry_entries:
            summary["performance_metrics"]["success_rate"] = successes / len(telemetry_entries)
        
        return {
            "result": {
                "entries": telemetry_entries,
                "summary": summary
            },
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return _error_response("TELEMETRY_QUERY_ERROR", str(e))

@router.get("/policies", dependencies=[Depends(verify_key)])
def get_safety_policies():
    """Get current safety policies for all action types with enhanced details"""
    
    safety_manager = get_safety_manager()
    policies = {}
    
    for action_type in ActionType:
        policy = safety_manager.get_policy(action_type)
        policies[action_type.value] = {
            "level": policy.level.value,
            "require_confirmation": policy.require_confirmation,
            "allow_dry_run": policy.allow_dry_run,
            "audit_required": policy.audit_required,
            "step_through_mode": policy.step_through_mode,
            "confirmation_mode": policy.confirmation_mode.value,
            "timeout_seconds": policy.timeout_seconds,
            "max_retries": policy.max_retries
        }
    
    return {
        "result": {
            "policies": policies,
            "config_path": safety_manager.config_path,
            "audit_log_path": safety_manager.audit_log_path,
            "telemetry_log_path": safety_manager.telemetry_log_path,
            "telemetry_enabled": safety_manager._telemetry_enabled
        },
        "timestamp": int(time.time() * 1000)
    }

@router.get("/status", dependencies=[Depends(verify_key)])
def get_safety_status():
    """Get comprehensive safety system status and statistics"""
    
    try:
        safety_manager = get_safety_manager()
        
        # Get audit summary
        audit_summary = safety_manager.get_audit_summary(24)  # Last 24 hours
        
        # Count pending actions
        pending_count = len(safety_manager.confirmation_manager.list_pending())
        
        # Count active debug sessions
        debug_sessions = len(safety_manager.step_through_debugger.active_sessions)
        
        return {
            "result": {
                "safety_enabled": True,
                "policies_loaded": len(safety_manager.policies),
                "audit_log_exists": os.path.exists(safety_manager.audit_log_path),
                "telemetry_log_exists": os.path.exists(safety_manager.telemetry_log_path),
                "telemetry_enabled": safety_manager._telemetry_enabled,
                "pending_confirmations": pending_count,
                "active_debug_sessions": debug_sessions,
                "audit_summary_24h": audit_summary,
                "available_levels": [level.value for level in SafetyLevel],
                "available_action_types": [action.value for action in ActionType],
                "available_confirmation_modes": [mode.value for mode in ConfirmationMode]
            },
            "timestamp": int(time.time() * 1000)
        }
        
    except Exception as e:
        return _error_response("STATUS_ERROR", str(e))

@router.post("/create_config", dependencies=[Depends(verify_key)])
def create_safety_config_endpoint():
    """Create enhanced default safety configuration file"""
    
    try:
        from utils.safety import create_safety_config
        config = create_safety_config()
        
        return {
            "result": {
                "status": "created",
                "config_path": "safety_config.json",
                "config": config,
                "version": config.get("version", "2.0")
            },
            "timestamp": int(time.time() * 1000)
        }
        
    except Exception as e:
        return _error_response("CONFIG_CREATE_ERROR", str(e))

@router.post("/telemetry/enable", dependencies=[Depends(verify_key)])
def enable_telemetry(enabled: bool = True):
    """Enable or disable telemetry collection"""
    
    try:
        safety_manager = get_safety_manager()
        safety_manager.enable_telemetry(enabled)
        
        return {
            "result": {
                "telemetry_enabled": enabled,
                "status": "updated"
            },
            "timestamp": int(time.time() * 1000)
        }
        
    except Exception as e:
        return _error_response("TELEMETRY_ENABLE_ERROR", str(e))

@router.delete("/audit/cleanup", dependencies=[Depends(verify_key)])
def cleanup_audit_logs(days_to_keep: int = 30):
    """Clean up old audit log entries"""
    
    try:
        safety_manager = get_safety_manager()
        cutoff_time = int((time.time() - (days_to_keep * 24 * 3600)) * 1000)
        
        entries_kept = 0
        entries_removed = 0
        
        # Read existing entries
        existing_entries = []
        try:
            with open(safety_manager.audit_log_path, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if entry.get("timestamp", 0) >= cutoff_time:
                            existing_entries.append(line)
                            entries_kept += 1
                        else:
                            entries_removed += 1
                    except json.JSONDecodeError:
                        entries_removed += 1
        except FileNotFoundError:
            pass
        
        # Write back only recent entries
        with open(safety_manager.audit_log_path, 'w') as f:
            f.writelines(existing_entries)
        
        return {
            "result": {
                "entries_kept": entries_kept,
                "entries_removed": entries_removed,
                "days_kept": days_to_keep,
                "cleanup_completed": True
            },
            "timestamp": int(time.time() * 1000)
        }
        
    except Exception as e:
        return _error_response("CLEANUP_ERROR", str(e))

@router.get("/export", dependencies=[Depends(verify_key)])
def export_safety_data(format: str = "json", include_telemetry: bool = False):
    """Export safety and audit data for compliance and analysis"""
    
    try:
        safety_manager = get_safety_manager()
        
        export_data = {
            "export_timestamp": int(time.time() * 1000),
            "format": format,
            "policies": {},
            "audit_summary": safety_manager.get_audit_summary(24 * 7),  # Last week
            "pending_actions": []
        }
        
        # Export policies
        for action_type in ActionType:
            policy = safety_manager.get_policy(action_type)
            export_data["policies"][action_type.value] = {
                "level": policy.level.value,
                "require_confirmation": policy.require_confirmation,
                "confirmation_mode": policy.confirmation_mode.value,
                "timeout_seconds": policy.timeout_seconds
            }
        
        # Export pending actions (sanitized)
        for pending in safety_manager.confirmation_manager.list_pending():
            export_data["pending_actions"].append({
                "action_id": pending.action_id,
                "endpoint": pending.endpoint,
                "action": pending.action,
                "created_at": pending.timestamp,
                "expires_at": pending.expires_at,
                "is_destructive": pending.safety_context.get("is_destructive", False)
            })
        
        # Include telemetry if requested
        if include_telemetry and safety_manager._telemetry_enabled:
            try:
                with open(safety_manager.telemetry_log_path, 'r') as f:
                    telemetry_entries = []
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            telemetry_entries.append(entry)
                        except json.JSONDecodeError:
                            continue
                    export_data["telemetry"] = telemetry_entries[-1000:]  # Last 1000 entries
            except FileNotFoundError:
                export_data["telemetry"] = []
        
        return {
            "result": export_data,
            "timestamp": int(time.time() * 1000)
        }
        
    except Exception as e:
        return _error_response("EXPORT_ERROR", str(e))