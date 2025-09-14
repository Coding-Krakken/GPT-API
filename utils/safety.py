"""
Enhanced safety and governance utilities for GUI automation.
Provides comprehensive confirmation policies, dry-run modes, audit logging, and step-through debugging.
"""

import time
import json
import os
import platform
import uuid
import threading
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path

class SafetyLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    STRICT = "strict"

class ActionType(Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELETE = "delete"
    SYSTEM = "system"
    NETWORK = "network"
    GUI_INPUT = "gui_input"  # New type for GUI interactions
    SCREEN_CAPTURE = "screen_capture"  # New type for screen operations

class ConfirmationMode(Enum):
    NONE = "none"  # No confirmation required
    AUTOMATIC = "automatic"  # Auto-approve safe actions
    PROMPT = "prompt"  # Require explicit confirmation
    STEP_THROUGH = "step_through"  # Step-by-step confirmation

@dataclass
class SafetyPolicy:
    level: SafetyLevel
    require_confirmation: bool
    allow_dry_run: bool
    audit_required: bool
    step_through_mode: bool
    confirmation_mode: ConfirmationMode = ConfirmationMode.PROMPT
    timeout_seconds: int = 300  # 5 minutes default
    max_retries: int = 3
    
@dataclass
class PendingAction:
    action_id: str
    endpoint: str
    action: str
    params: Dict[str, Any]
    timestamp: float
    expires_at: float
    safety_context: Dict[str, Any]
    confirmed: bool = False
    confirmation_token: Optional[str] = None

class ConfirmationManager:
    """Manages pending actions requiring confirmation"""
    
    def __init__(self):
        self.pending_actions: Dict[str, PendingAction] = {}
        self._lock = threading.Lock()
    
    def create_pending_action(self, endpoint: str, action: str, params: Dict[str, Any], 
                            safety_context: Dict[str, Any], timeout_seconds: int = 300) -> str:
        """Create a pending action requiring confirmation"""
        action_id = str(uuid.uuid4())
        expires_at = time.time() + timeout_seconds
        confirmation_token = str(uuid.uuid4())[:8]  # Short token for user convenience
        
        pending = PendingAction(
            action_id=action_id,
            endpoint=endpoint,
            action=action,
            params=params,
            timestamp=time.time(),
            expires_at=expires_at,
            safety_context=safety_context,
            confirmation_token=confirmation_token
        )
        
        with self._lock:
            self.pending_actions[action_id] = pending
        
        return action_id
    
    def confirm_action(self, action_id: str, confirmation_token: Optional[str] = None) -> bool:
        """Confirm a pending action"""
        with self._lock:
            if action_id not in self.pending_actions:
                return False
            
            pending = self.pending_actions[action_id]
            
            # Check expiration
            if time.time() > pending.expires_at:
                del self.pending_actions[action_id]
                return False
            
            # Check token if provided
            if confirmation_token and pending.confirmation_token != confirmation_token:
                return False
            
            pending.confirmed = True
            return True
    
    def get_pending_action(self, action_id: str) -> Optional[PendingAction]:
        """Get pending action details"""
        with self._lock:
            return self.pending_actions.get(action_id)
    
    def cleanup_expired(self):
        """Remove expired pending actions"""
        now = time.time()
        with self._lock:
            expired_ids = [aid for aid, action in self.pending_actions.items() 
                          if now > action.expires_at]
            for aid in expired_ids:
                del self.pending_actions[aid]
    
    def list_pending(self) -> List[PendingAction]:
        """List all pending actions"""
        self.cleanup_expired()
        with self._lock:
            return list(self.pending_actions.values())

class StepThroughDebugger:
    """Handles step-through debugging mode for actions"""
    
    def __init__(self):
        self.active_sessions: Dict[str, Dict] = {}
        self._lock = threading.Lock()
    
    def start_session(self, session_id: str, action_sequence: List[Dict]) -> Dict:
        """Start a step-through debugging session"""
        with self._lock:
            self.active_sessions[session_id] = {
                "id": session_id,
                "sequence": action_sequence,
                "current_step": 0,
                "status": "started",
                "breakpoints": [],
                "variables": {},
                "created_at": time.time()
            }
        return self.active_sessions[session_id]
    
    def next_step(self, session_id: str) -> Optional[Dict]:
        """Execute next step in debugging session"""
        with self._lock:
            if session_id not in self.active_sessions:
                return None
            
            session = self.active_sessions[session_id]
            
            if session["current_step"] >= len(session["sequence"]):
                session["status"] = "completed"
                return None
            
            current_action = session["sequence"][session["current_step"]]
            session["current_step"] += 1
            
            return {
                "session_id": session_id,
                "step": session["current_step"],
                "total_steps": len(session["sequence"]),
                "action": current_action,
                "status": session["status"]
            }
    
    def add_breakpoint(self, session_id: str, step_number: int):
        """Add breakpoint at specific step"""
        with self._lock:
            if session_id in self.active_sessions:
                self.active_sessions[session_id]["breakpoints"].append(step_number)
    
    def set_variable(self, session_id: str, key: str, value: Any):
        """Set debug variable"""
        with self._lock:
            if session_id in self.active_sessions:
                self.active_sessions[session_id]["variables"][key] = value
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get debugging session details"""
        with self._lock:
            return self.active_sessions.get(session_id)

class SafetyManager:
    """Enhanced centralized safety and governance manager"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.path.join(os.getcwd(), "safety_config.json")
        self.audit_log_path = os.path.join(os.getcwd(), "audit.log")
        self.telemetry_log_path = os.path.join(os.getcwd(), "telemetry.log")
        self.policies = self._load_policies()
        self.confirmation_manager = ConfirmationManager()
        self.step_through_debugger = StepThroughDebugger()
        self._telemetry_enabled = True
        self._audit_lock = threading.Lock()
        
    def _load_policies(self) -> Dict[ActionType, SafetyPolicy]:
        """Load enhanced safety policies from configuration"""
        default_policies = {
            ActionType.READ: SafetyPolicy(
                level=SafetyLevel.LOW,
                require_confirmation=False,
                allow_dry_run=True,
                audit_required=True,
                step_through_mode=False,
                confirmation_mode=ConfirmationMode.NONE
            ),
            ActionType.WRITE: SafetyPolicy(
                level=SafetyLevel.MEDIUM,
                require_confirmation=True,
                allow_dry_run=True,
                audit_required=True,
                step_through_mode=False,
                confirmation_mode=ConfirmationMode.PROMPT
            ),
            ActionType.EXECUTE: SafetyPolicy(
                level=SafetyLevel.MEDIUM,
                require_confirmation=True,
                allow_dry_run=True,
                audit_required=True,
                step_through_mode=False,
                confirmation_mode=ConfirmationMode.PROMPT
            ),
            ActionType.DELETE: SafetyPolicy(
                level=SafetyLevel.STRICT,
                require_confirmation=True,
                allow_dry_run=True,
                audit_required=True,
                step_through_mode=True,
                confirmation_mode=ConfirmationMode.STEP_THROUGH
            ),
            ActionType.SYSTEM: SafetyPolicy(
                level=SafetyLevel.STRICT,
                require_confirmation=True,
                allow_dry_run=True,
                audit_required=True,
                step_through_mode=True,
                confirmation_mode=ConfirmationMode.STEP_THROUGH
            ),
            ActionType.NETWORK: SafetyPolicy(
                level=SafetyLevel.MEDIUM,
                require_confirmation=False,
                allow_dry_run=True,
                audit_required=True,
                step_through_mode=False,
                confirmation_mode=ConfirmationMode.AUTOMATIC
            ),
            ActionType.GUI_INPUT: SafetyPolicy(
                level=SafetyLevel.MEDIUM,
                require_confirmation=True,
                allow_dry_run=True,
                audit_required=True,
                step_through_mode=False,
                confirmation_mode=ConfirmationMode.PROMPT
            ),
            ActionType.SCREEN_CAPTURE: SafetyPolicy(
                level=SafetyLevel.LOW,
                require_confirmation=False,
                allow_dry_run=True,
                audit_required=True,
                step_through_mode=False,
                confirmation_mode=ConfirmationMode.NONE
            )
        }
        
        # Try to load from config file
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    # Update default policies with config
                    for action_str, policy_data in config.get("policies", {}).items():
                        try:
                            action_type = ActionType(action_str)
                            default_policies[action_type] = SafetyPolicy(
                                level=SafetyLevel(policy_data.get("level", "medium")),
                                require_confirmation=policy_data.get("require_confirmation", True),
                                allow_dry_run=policy_data.get("allow_dry_run", True),
                                audit_required=policy_data.get("audit_required", True),
                                step_through_mode=policy_data.get("step_through_mode", False),
                                confirmation_mode=ConfirmationMode(policy_data.get("confirmation_mode", "prompt")),
                                timeout_seconds=policy_data.get("timeout_seconds", 300),
                                max_retries=policy_data.get("max_retries", 3)
                            )
                        except (ValueError, KeyError) as e:
                            self._log_audit("WARNING", f"Invalid policy config for {action_str}: {e}")
            
            except Exception as e:
                self._log_audit("ERROR", f"Failed to load safety config: {e}")
        
        return default_policies
    
    def get_policy(self, action_type: ActionType) -> SafetyPolicy:
        """Get safety policy for action type"""
        return self.policies.get(action_type, self.policies[ActionType.EXECUTE])
    
    def is_destructive_action(self, action: str, params: Dict[str, Any]) -> bool:
        """Determine if an action is potentially destructive"""
        destructive_patterns = [
            # File operations
            "delete", "remove", "rm", "unlink", "truncate",
            # System operations  
            "shutdown", "reboot", "halt", "kill", "killall", "terminate",
            # Disk operations
            "format", "fdisk", "mkfs", "dd", "wipe",
            # Network operations
            "wget", "curl", "ssh", "scp", "rsync",
            # Application operations
            "close", "quit", "exit", "force_quit",
            # Dangerous GUI operations
            "alt+f4", "cmd+q", "ctrl+alt+delete", "force_close"
        ]
        
        action_lower = action.lower()
        for pattern in destructive_patterns:
            if pattern in action_lower:
                return True
                
        # Check parameters for destructive content
        param_str = json.dumps(params).lower()
        for pattern in destructive_patterns:
            if pattern in param_str:
                return True
        
        # Check for dangerous key combinations
        if "keys" in params:
            keys = [k.lower() for k in params.get("keys", [])]
            dangerous_combos = [
                ["ctrl", "alt", "delete"],
                ["cmd", "option", "esc"],
                ["alt", "f4"],
                ["ctrl", "shift", "esc"]
            ]
            for combo in dangerous_combos:
                if all(key in keys for key in combo):
                    return True
                
        return False
    
    def classify_action(self, endpoint: str, action: str, params: Dict[str, Any]) -> ActionType:
        """Enhanced action classification"""
        endpoint_lower = endpoint.lower()
        action_lower = action.lower()
        
        if "screen" in endpoint_lower:
            if "capture" in action_lower or "ocr" in action_lower:
                return ActionType.SCREEN_CAPTURE
            return ActionType.READ
        elif "input" in endpoint_lower:
            if self.is_destructive_action(action, params):
                return ActionType.DELETE
            return ActionType.GUI_INPUT
        elif "file" in endpoint_lower:
            if action_lower in ["read", "list", "stat", "exists"]:
                return ActionType.READ
            elif action_lower in ["delete", "remove", "unlink"]:
                return ActionType.DELETE
            else:
                return ActionType.WRITE
        elif "shell" in endpoint_lower:
            if self.is_destructive_action(action, params):
                return ActionType.DELETE
            return ActionType.SYSTEM
        elif "apps" in endpoint_lower:
            if action_lower in ["launch", "list", "list_windows"]:
                return ActionType.EXECUTE
            elif action_lower in ["kill", "force_quit", "terminate"]:
                return ActionType.DELETE
            return ActionType.SYSTEM
        elif "git" in endpoint_lower or "package" in endpoint_lower:
            return ActionType.NETWORK
        
        return ActionType.EXECUTE
    def check_safety(self, endpoint: str, action: str, params: Dict[str, Any], 
                    dry_run: bool = False, confirmed: bool = False, 
                    confirmation_token: Optional[str] = None) -> Dict[str, Any]:
        """Enhanced safety check with confirmation management"""
        action_type = self.classify_action(endpoint, action, params)
        policy = self.get_policy(action_type)
        
        # Enhanced safety context
        safety_context = {
            "endpoint": endpoint,
            "action": action,
            "action_type": action_type.value,
            "policy_level": policy.level.value,
            "is_destructive": self.is_destructive_action(action, params),
            "requires_confirmation": policy.require_confirmation,
            "confirmation_mode": policy.confirmation_mode.value,
            "allows_dry_run": policy.allow_dry_run,
            "requires_audit": policy.audit_required,
            "step_through_mode": policy.step_through_mode,
            "platform": platform.system(),
            "timestamp": time.time()
        }
        
        result = {
            "safe": True,
            "action_type": action_type.value,
            "policy": asdict(policy),
            "context": safety_context,
            "confirmation_required": False,
            "action_id": None,
            "confirmation_token": None
        }
        
        # Skip confirmation for dry runs or already confirmed actions
        if dry_run:
            result["reason"] = "DRY_RUN_MODE"
            return result
        
        # Check if confirmation is required
        if policy.require_confirmation and not confirmed:
            # Check if this is a confirmation attempt
            if confirmation_token:
                # Find pending action with this token
                for pending in self.confirmation_manager.list_pending():
                    if (pending.confirmation_token == confirmation_token and 
                        pending.endpoint == endpoint and pending.action == action):
                        if self.confirmation_manager.confirm_action(pending.action_id, confirmation_token):
                            result["safe"] = True
                            result["reason"] = "CONFIRMED_VIA_TOKEN"
                            return result
                
                result["safe"] = False
                result["reason"] = "INVALID_CONFIRMATION_TOKEN"
                result["message"] = "Invalid or expired confirmation token"
                return result
            
            # Create pending action for confirmation
            action_id = self.confirmation_manager.create_pending_action(
                endpoint, action, params, safety_context, policy.timeout_seconds
            )
            
            pending = self.confirmation_manager.get_pending_action(action_id)
            
            result["safe"] = False
            result["reason"] = "CONFIRMATION_REQUIRED"
            result["confirmation_required"] = True
            result["action_id"] = action_id
            result["confirmation_token"] = pending.confirmation_token if pending else None
            result["confirmation_mode"] = policy.confirmation_mode.value
            result["expires_in_seconds"] = policy.timeout_seconds
            result["message"] = self._generate_confirmation_message(action_type, policy, safety_context)
            
            return result
        
        # Check dry run support
        if dry_run and not policy.allow_dry_run:
            result["safe"] = False
            result["reason"] = "DRY_RUN_NOT_SUPPORTED"
            result["message"] = "Dry run mode not supported for this action type"
            return result
        
        return result
    
    def _generate_confirmation_message(self, action_type: ActionType, policy: SafetyPolicy, 
                                     context: Dict[str, Any]) -> str:
        """Generate appropriate confirmation message"""
        endpoint = context.get("endpoint", "unknown")
        action = context.get("action", "unknown")
        is_destructive = context.get("is_destructive", False)
        
        base_msg = f"Confirm {endpoint}.{action}"
        
        if is_destructive:
            base_msg += " (DESTRUCTIVE ACTION)"
        
        if policy.level == SafetyLevel.STRICT:
            base_msg += " - This is a high-risk operation"
        elif policy.level == SafetyLevel.MEDIUM:
            base_msg += " - This requires approval"
        
        if policy.step_through_mode:
            base_msg += " - Will execute in step-through mode"
        
        return base_msg
    
    def enable_telemetry(self, enabled: bool = True):
        """Enable or disable telemetry collection"""
        self._telemetry_enabled = enabled
        self._log_audit("INFO", f"Telemetry {'enabled' if enabled else 'disabled'}")
    
    def log_telemetry(self, event_type: str, data: Dict[str, Any]):
        """Log telemetry data"""
        if not self._telemetry_enabled:
            return
        
        telemetry_entry = {
            "timestamp": int(time.time() * 1000),
            "event_type": event_type,
            "platform": platform.system(),
            "data": data
        }
        
        try:
            with open(self.telemetry_log_path, 'a') as f:
                f.write(json.dumps(telemetry_entry) + '\n')
        except Exception as e:
            self._log_audit("WARNING", f"Failed to write telemetry: {e}")
    
    def _log_audit(self, level: str, message: str, details: Optional[Dict] = None):
        """Thread-safe audit logging"""
        timestamp = int(time.time() * 1000)
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message,
            "platform": platform.system(),
            "details": details or {}
        }
        
        with self._audit_lock:
            try:
                with open(self.audit_log_path, 'a') as f:
                    f.write(json.dumps(log_entry) + '\n')
            except Exception as e:
                print(f"Failed to write audit log: {e}")
    
    def log_action(self, endpoint: str, action: str, params: Dict[str, Any], 
                  result: Dict[str, Any], dry_run: bool = False):
        """Enhanced action logging with telemetry"""
        action_type = self.classify_action(endpoint, action, params)
        
        details = {
            "endpoint": endpoint,
            "action": action,
            "params": params,
            "result": result,
            "dry_run": dry_run,
            "action_type": action_type.value,
            "is_destructive": self.is_destructive_action(action, params)
        }
        
        level = "INFO" if dry_run else "ACTION"
        message = f"{'DRY-RUN' if dry_run else 'EXECUTED'}: {endpoint}.{action}"
        
        self._log_audit(level, message, details)
        
        # Log telemetry
        if not dry_run:
            self.log_telemetry("action_executed", {
                "endpoint": endpoint,
                "action": action,
                "action_type": action_type.value,
                "success": "errors" not in result,
                "duration_ms": result.get("latency_ms", 0)
            })
    
    def get_audit_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get audit log summary for specified time period"""
        cutoff_time = int((time.time() - (hours * 3600)) * 1000)
        summary = {
            "period_hours": hours,
            "total_entries": 0,
            "by_level": {},
            "by_action_type": {},
            "by_endpoint": {},
            "destructive_actions": 0,
            "dry_runs": 0
        }
        
        try:
            with open(self.audit_log_path, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if entry.get("timestamp", 0) < cutoff_time:
                            continue
                            
                        summary["total_entries"] += 1
                        
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
                            
                            if details.get("dry_run"):
                                summary["dry_runs"] += 1
                    
                    except json.JSONDecodeError:
                        continue
        
        except FileNotFoundError:
            pass
        
        return summary

def create_safety_config():
    """Create enhanced default safety configuration file"""
    config = {
        "version": "2.0",
        "policies": {
            "read": {
                "level": "low",
                "require_confirmation": False,
                "allow_dry_run": True,
                "audit_required": True,
                "step_through_mode": False,
                "confirmation_mode": "none",
                "timeout_seconds": 300,
                "max_retries": 3
            },
            "write": {
                "level": "medium", 
                "require_confirmation": True,
                "allow_dry_run": True,
                "audit_required": True,
                "step_through_mode": False,
                "confirmation_mode": "prompt",
                "timeout_seconds": 300,
                "max_retries": 3
            },
            "execute": {
                "level": "medium",
                "require_confirmation": True,
                "allow_dry_run": True,
                "audit_required": True,
                "step_through_mode": False,
                "confirmation_mode": "prompt",
                "timeout_seconds": 300,
                "max_retries": 3
            },
            "delete": {
                "level": "strict",
                "require_confirmation": True,
                "allow_dry_run": True,
                "audit_required": True,
                "step_through_mode": True,
                "confirmation_mode": "step_through",
                "timeout_seconds": 600,
                "max_retries": 1
            },
            "system": {
                "level": "strict",
                "require_confirmation": True,
                "allow_dry_run": True,
                "audit_required": True,
                "step_through_mode": True,
                "confirmation_mode": "step_through",
                "timeout_seconds": 600,
                "max_retries": 1
            },
            "network": {
                "level": "medium",
                "require_confirmation": False,
                "allow_dry_run": True,
                "audit_required": True,
                "step_through_mode": False,
                "confirmation_mode": "automatic",
                "timeout_seconds": 300,
                "max_retries": 3
            },
            "gui_input": {
                "level": "medium",
                "require_confirmation": True,
                "allow_dry_run": True,
                "audit_required": True,
                "step_through_mode": False,
                "confirmation_mode": "prompt",
                "timeout_seconds": 300,
                "max_retries": 3
            },
            "screen_capture": {
                "level": "low",
                "require_confirmation": False,
                "allow_dry_run": True,
                "audit_required": True,
                "step_through_mode": False,
                "confirmation_mode": "none",
                "timeout_seconds": 300,
                "max_retries": 3
            }
        },
        "global_settings": {
            "telemetry_enabled": True,
            "audit_retention_days": 30,
            "max_pending_actions": 100,
            "default_timeout_seconds": 300
        }
    }
    
    with open("safety_config.json", 'w') as f:
        json.dump(config, f, indent=2)
    
    return config

# Global safety manager instance
_safety_manager = None

def get_safety_manager() -> SafetyManager:
    """Get global safety manager instance"""
    global _safety_manager
    if _safety_manager is None:
        _safety_manager = SafetyManager()
    return _safety_manager

def safety_check(endpoint: str, action: str, params: Dict[str, Any], 
                dry_run: bool = False, confirmed: bool = False, 
                confirmation_token: Optional[str] = None) -> Dict[str, Any]:
    """Enhanced convenience function for safety checks"""
    return get_safety_manager().check_safety(endpoint, action, params, dry_run, confirmed, confirmation_token)

def log_action(endpoint: str, action: str, params: Dict[str, Any], 
               result: Dict[str, Any], dry_run: bool = False):
    """Convenience function for action logging"""
    get_safety_manager().log_action(endpoint, action, params, result, dry_run)

def create_confirmation(endpoint: str, action: str, params: Dict[str, Any]) -> str:
    """Create a pending action requiring confirmation"""
    safety_manager = get_safety_manager()
    action_type = safety_manager.classify_action(endpoint, action, params)
    policy = safety_manager.get_policy(action_type)
    
    safety_context = {
        "endpoint": endpoint,
        "action": action,
        "action_type": action_type.value,
        "is_destructive": safety_manager.is_destructive_action(action, params)
    }
    
    return safety_manager.confirmation_manager.create_pending_action(
        endpoint, action, params, safety_context, policy.timeout_seconds
    )

def confirm_action(action_id: str, confirmation_token: Optional[str] = None) -> bool:
    """Confirm a pending action"""
    return get_safety_manager().confirmation_manager.confirm_action(action_id, confirmation_token)

def list_pending_actions() -> List[PendingAction]:
    """List all pending actions requiring confirmation"""
    return get_safety_manager().confirmation_manager.list_pending()