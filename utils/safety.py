"""
Safety and governance utilities for GUI automation.
Provides confirmation policies, dry-run modes, and audit logging.
"""

import time
import json
import os
import platform
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass
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

@dataclass
class SafetyPolicy:
    level: SafetyLevel
    require_confirmation: bool
    allow_dry_run: bool
    audit_required: bool
    step_through_mode: bool
    
class SafetyManager:
    """Centralized safety and governance manager"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.path.join(os.getcwd(), "safety_config.json")
        self.audit_log_path = os.path.join(os.getcwd(), "audit.log")
        self.policies = self._load_policies()
        
    def _load_policies(self) -> Dict[ActionType, SafetyPolicy]:
        """Load safety policies from configuration"""
        default_policies = {
            ActionType.READ: SafetyPolicy(
                level=SafetyLevel.LOW,
                require_confirmation=False,
                allow_dry_run=True,
                audit_required=True,
                step_through_mode=False
            ),
            ActionType.WRITE: SafetyPolicy(
                level=SafetyLevel.MEDIUM,
                require_confirmation=True,
                allow_dry_run=True,
                audit_required=True,
                step_through_mode=False
            ),
            ActionType.EXECUTE: SafetyPolicy(
                level=SafetyLevel.MEDIUM,
                require_confirmation=True,
                allow_dry_run=True,
                audit_required=True,
                step_through_mode=False
            ),
            ActionType.DELETE: SafetyPolicy(
                level=SafetyLevel.STRICT,
                require_confirmation=True,
                allow_dry_run=True,
                audit_required=True,
                step_through_mode=True
            ),
            ActionType.SYSTEM: SafetyPolicy(
                level=SafetyLevel.STRICT,
                require_confirmation=True,
                allow_dry_run=True,
                audit_required=True,
                step_through_mode=True
            ),
            ActionType.NETWORK: SafetyPolicy(
                level=SafetyLevel.MEDIUM,
                require_confirmation=False,
                allow_dry_run=True,
                audit_required=True,
                step_through_mode=False
            )
        }
        
        # Try to load from config file
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    # Update default policies with config
                    for action_str, policy_data in config.get("policies", {}).items():
                        action_type = ActionType(action_str)
                        default_policies[action_type] = SafetyPolicy(
                            level=SafetyLevel(policy_data.get("level", "medium")),
                            require_confirmation=policy_data.get("require_confirmation", True),
                            allow_dry_run=policy_data.get("allow_dry_run", True),
                            audit_required=policy_data.get("audit_required", True),
                            step_through_mode=policy_data.get("step_through_mode", False)
                        )
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
            "delete", "remove", "rm", "unlink",
            # System operations  
            "shutdown", "reboot", "halt", "kill", "killall",
            # Disk operations
            "format", "fdisk", "mkfs", "dd",
            # Network operations
            "wget", "curl", "ssh", "scp",
            # Application operations
            "close", "quit", "exit", "terminate"
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
                
        return False
    
    def classify_action(self, endpoint: str, action: str, params: Dict[str, Any]) -> ActionType:
        """Classify action type based on endpoint and parameters"""
        endpoint_lower = endpoint.lower()
        action_lower = action.lower()
        
        if "screen" in endpoint_lower or "capture" in action_lower:
            return ActionType.READ
        elif "input" in endpoint_lower:
            if self.is_destructive_action(action, params):
                return ActionType.DELETE
            else:
                return ActionType.EXECUTE
        elif "file" in endpoint_lower:
            if action_lower in ["read", "list", "stat"]:
                return ActionType.READ
            elif action_lower in ["delete", "remove"]:
                return ActionType.DELETE
            else:
                return ActionType.WRITE
        elif "shell" in endpoint_lower or "apps" in endpoint_lower:
            if self.is_destructive_action(action, params):
                return ActionType.DELETE
            else:
                return ActionType.SYSTEM
        elif "git" in endpoint_lower or "package" in endpoint_lower:
            return ActionType.NETWORK
        
        return ActionType.EXECUTE
    
    def check_safety(self, endpoint: str, action: str, params: Dict[str, Any], 
                    dry_run: bool = False, confirmed: bool = False) -> Dict[str, Any]:
        """Check if action is safe to execute"""
        action_type = self.classify_action(endpoint, action, params)
        policy = self.get_policy(action_type)
        
        result = {
            "safe": True,
            "action_type": action_type.value,
            "policy_level": policy.level.value,
            "requires_confirmation": policy.require_confirmation,
            "allows_dry_run": policy.allow_dry_run,
            "requires_audit": policy.audit_required,
            "step_through_mode": policy.step_through_mode,
            "is_destructive": self.is_destructive_action(action, params)
        }
        
        # Check confirmation requirement
        if policy.require_confirmation and not confirmed and not dry_run:
            result["safe"] = False
            result["reason"] = "CONFIRMATION_REQUIRED"
            result["message"] = f"Action requires confirmation due to {policy.level.value} safety level"
        
        # Check dry run support
        if dry_run and not policy.allow_dry_run:
            result["safe"] = False
            result["reason"] = "DRY_RUN_NOT_SUPPORTED"
            result["message"] = "Dry run mode not supported for this action type"
        
        return result
    
    def _log_audit(self, level: str, message: str, details: Optional[Dict] = None):
        """Log audit entry"""
        timestamp = int(time.time() * 1000)
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message,
            "platform": platform.system(),
            "details": details or {}
        }
        
        try:
            with open(self.audit_log_path, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            print(f"Failed to write audit log: {e}")
    
    def log_action(self, endpoint: str, action: str, params: Dict[str, Any], 
                  result: Dict[str, Any], dry_run: bool = False):
        """Log executed action for audit trail"""
        details = {
            "endpoint": endpoint,
            "action": action,
            "params": params,
            "result": result,
            "dry_run": dry_run,
            "action_type": self.classify_action(endpoint, action, params).value
        }
        
        level = "INFO" if dry_run else "ACTION"
        message = f"{'DRY-RUN' if dry_run else 'EXECUTED'}: {endpoint}.{action}"
        
        self._log_audit(level, message, details)

def create_safety_config():
    """Create default safety configuration file"""
    config = {
        "policies": {
            "read": {
                "level": "low",
                "require_confirmation": False,
                "allow_dry_run": True,
                "audit_required": True,
                "step_through_mode": False
            },
            "write": {
                "level": "medium", 
                "require_confirmation": True,
                "allow_dry_run": True,
                "audit_required": True,
                "step_through_mode": False
            },
            "execute": {
                "level": "medium",
                "require_confirmation": True,
                "allow_dry_run": True,
                "audit_required": True,
                "step_through_mode": False
            },
            "delete": {
                "level": "strict",
                "require_confirmation": True,
                "allow_dry_run": True,
                "audit_required": True,
                "step_through_mode": True
            },
            "system": {
                "level": "strict",
                "require_confirmation": True,
                "allow_dry_run": True,
                "audit_required": True,
                "step_through_mode": True
            },
            "network": {
                "level": "medium",
                "require_confirmation": False,
                "allow_dry_run": True,
                "audit_required": True,
                "step_through_mode": False
            }
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
                dry_run: bool = False, confirmed: bool = False) -> Dict[str, Any]:
    """Convenience function for safety checks"""
    return get_safety_manager().check_safety(endpoint, action, params, dry_run, confirmed)

def log_action(endpoint: str, action: str, params: Dict[str, Any], 
               result: Dict[str, Any], dry_run: bool = False):
    """Convenience function for action logging"""
    get_safety_manager().log_action(endpoint, action, params, result, dry_run)