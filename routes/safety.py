"""
Safety and governance endpoints for GUI automation.
Provides confirmation flows, audit logging, and step-through modes.
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import time
import json
import os
from utils.auth import verify_key
from utils.safety import get_safety_manager, safety_check, SafetyLevel, ActionType

router = APIRouter()

class SafetyCheckRequest(BaseModel):
    endpoint: str
    action: str
    params: Dict[str, Any]
    dry_run: Optional[bool] = False
    confirmed: Optional[bool] = False

class ConfirmationRequest(BaseModel):
    action_id: str
    confirmed: bool
    reason: Optional[str] = None

class AuditQueryRequest(BaseModel):
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    level: Optional[str] = None
    endpoint: Optional[str] = None
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
    Check if an action is safe to execute based on safety policies.
    Returns safety assessment and required confirmations.
    """
    start_time = time.time()
    
    try:
        safety_result = safety_check(
            req.endpoint, 
            req.action, 
            req.params, 
            req.dry_run, 
            req.confirmed
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
    Handle user confirmations for actions requiring approval.
    Manages confirmation workflow and temporary approvals.
    """
    start_time = time.time()
    
    # In a full implementation, this would store confirmation tokens
    # and match them with pending actions
    
    result = {
        "action_id": req.action_id,
        "confirmed": req.confirmed,
        "reason": req.reason,
        "status": "accepted" if req.confirmed else "rejected",
        "expires_at": int(time.time() * 1000) + 300000  # 5 minutes
    }
    
    return {
        "result": result,
        "timestamp": int(time.time() * 1000),
        "latency_ms": int((time.time() - start_time) * 1000)
    }

@router.get("/policies", dependencies=[Depends(verify_key)])
def get_safety_policies():
    """Get current safety policies for all action types"""
    
    safety_manager = get_safety_manager()
    policies = {}
    
    for action_type in ActionType:
        policy = safety_manager.get_policy(action_type)
        policies[action_type.value] = {
            "level": policy.level.value,
            "require_confirmation": policy.require_confirmation,
            "allow_dry_run": policy.allow_dry_run,
            "audit_required": policy.audit_required,
            "step_through_mode": policy.step_through_mode
        }
    
    return {
        "result": {
            "policies": policies,
            "config_path": safety_manager.config_path,
            "audit_log_path": safety_manager.audit_log_path
        },
        "timestamp": int(time.time() * 1000)
    }

@router.post("/audit", dependencies=[Depends(verify_key)])
def query_audit_log(req: AuditQueryRequest, response: Response):
    """
    Query audit log entries with filtering and pagination.
    Provides transparency and compliance tracking.
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
        
        return {
            "result": {
                "entries": audit_entries[:req.limit],
                "total_found": len(audit_entries),
                "filters_applied": {
                    "start_time": req.start_time,
                    "end_time": req.end_time,
                    "level": req.level,
                    "endpoint": req.endpoint,
                    "limit": req.limit
                }
            },
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return _error_response("AUDIT_QUERY_ERROR", str(e))

@router.get("/status", dependencies=[Depends(verify_key)])
def get_safety_status():
    """Get current safety system status and statistics"""
    
    safety_manager = get_safety_manager()
    
    # Count audit entries by level
    audit_stats = {"INFO": 0, "ACTION": 0, "ERROR": 0, "WARNING": 0}
    total_entries = 0
    
    try:
        with open(safety_manager.audit_log_path, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    level = entry.get("level", "INFO")
                    audit_stats[level] = audit_stats.get(level, 0) + 1
                    total_entries += 1
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    
    return {
        "result": {
            "safety_enabled": True,
            "policies_loaded": len(safety_manager.policies),
            "audit_log_exists": os.path.exists(safety_manager.audit_log_path),
            "total_audit_entries": total_entries,
            "audit_stats": audit_stats,
            "available_levels": [level.value for level in SafetyLevel],
            "available_action_types": [action.value for action in ActionType]
        },
        "timestamp": int(time.time() * 1000)
    }

@router.post("/create_config", dependencies=[Depends(verify_key)])
def create_safety_config_endpoint():
    """Create default safety configuration file"""
    
    try:
        from utils.safety import create_safety_config
        config = create_safety_config()
        
        return {
            "result": {
                "status": "created",
                "config_path": "safety_config.json",
                "config": config
            },
            "timestamp": int(time.time() * 1000)
        }
        
    except Exception as e:
        return _error_response("CONFIG_CREATE_ERROR", str(e))