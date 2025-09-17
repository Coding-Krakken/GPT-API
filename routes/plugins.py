"""
Plugin system endpoints for GUI automation extensibility.
Provides dynamic loading of new backends, toolkits, and capabilities.
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union
import time
import json
import os
import importlib
import sys
from pathlib import Path
from utils.auth import verify_key
from utils.safety import safety_check, log_action

router = APIRouter()

# Plugin registry and management
_loaded_plugins = {}
_plugin_registry = {}
_plugin_hooks = {}

class PluginLoadRequest(BaseModel):
    action: str  # "load", "unload", "reload"
    plugin_name: str
    plugin_path: Optional[str] = None  # Path to plugin file/directory
    plugin_config: Optional[Dict[str, Any]] = None
    auto_enable: Optional[bool] = True
    dry_run: Optional[bool] = False

class PluginCapabilityRequest(BaseModel):
    action: str  # "list", "query", "enable", "disable"
    plugin_name: Optional[str] = None
    capability_name: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None

class PluginHookRequest(BaseModel):
    action: str  # "register", "unregister", "trigger"
    hook_name: str
    plugin_name: Optional[str] = None
    callback_function: Optional[str] = None
    event_data: Optional[Dict[str, Any]] = None

def _error_response(code: str, message: str, extra: Optional[Dict] = None) -> Dict:
    """Create standardized error response"""
    result = {
        "errors": [{"code": code, "message": message}],
        "timestamp": int(time.time() * 1000)
    }
    if extra:
        result.update(extra)
    return result

def _validate_plugin_structure(plugin_path: str) -> Dict[str, Any]:
    """Validate plugin structure and metadata"""
    plugin_info = {
        "valid": False,
        "name": None,
        "version": None,
        "description": None,
        "capabilities": [],
        "dependencies": [],
        "hooks": [],
        "errors": []
    }
    
    try:
        if not os.path.exists(plugin_path):
            plugin_info["errors"].append("Plugin path does not exist")
            return plugin_info
        
        # Check for plugin manifest
        manifest_path = os.path.join(plugin_path, "plugin.json") if os.path.isdir(plugin_path) else None
        
        if manifest_path and os.path.exists(manifest_path):
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
                
            plugin_info.update({
                "name": manifest.get("name"),
                "version": manifest.get("version"),
                "description": manifest.get("description"),
                "capabilities": manifest.get("capabilities", []),
                "dependencies": manifest.get("dependencies", []),
                "hooks": manifest.get("hooks", [])
            })
        
        # Check for main plugin file
        main_file = os.path.join(plugin_path, "__init__.py") if os.path.isdir(plugin_path) else plugin_path
        
        if os.path.exists(main_file) and main_file.endswith('.py'):
            plugin_info["valid"] = True
        else:
            plugin_info["errors"].append("No valid Python plugin file found")
    
    except Exception as e:
        plugin_info["errors"].append(f"Plugin validation error: {str(e)}")
    
    return plugin_info

def _load_plugin_module(plugin_path: str, plugin_name: str):
    """Dynamically load plugin module"""
    try:
        # Add plugin directory to Python path
        plugin_dir = os.path.dirname(plugin_path) if os.path.isfile(plugin_path) else plugin_path
        if plugin_dir not in sys.path:
            sys.path.insert(0, plugin_dir)
        
        # Import the plugin module
        if os.path.isdir(plugin_path):
            spec = importlib.util.spec_from_file_location(plugin_name, os.path.join(plugin_path, "__init__.py"))
        else:
            spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        return module
    
    except Exception as e:
        raise Exception(f"Failed to load plugin module: {str(e)}")

def _initialize_plugin(plugin_module, plugin_config: Dict[str, Any] = None):
    """Initialize loaded plugin"""
    try:
        # Look for plugin initialization function
        if hasattr(plugin_module, 'initialize_plugin'):
            return plugin_module.initialize_plugin(plugin_config or {})
        elif hasattr(plugin_module, 'init'):
            return plugin_module.init(plugin_config or {})
        else:
            # Basic initialization
            return {
                "initialized": True,
                "capabilities": getattr(plugin_module, 'CAPABILITIES', []),
                "hooks": getattr(plugin_module, 'HOOKS', [])
            }
    
    except Exception as e:
        raise Exception(f"Plugin initialization failed: {str(e)}")

@router.post("/load", dependencies=[Depends(verify_key)])
def load_plugin(req: PluginLoadRequest, response: Response):
    """
    Load, unload, or reload plugins dynamically.
    Extends system capabilities with custom backends and toolkits.
    """
    start_time = time.time()
    
    if req.action not in ["load", "unload", "reload"]:
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    # Safety check
    safety_result = safety_check("/plugins", req.action, req.dict(), req.dry_run)
    if not safety_result["safe"]:
        return _error_response("SAFETY_VIOLATION", safety_result["message"], {"safety": safety_result})
    
    result = {
        "action": req.action,
        "plugin_name": req.plugin_name,
        "plugin_path": req.plugin_path,
        "auto_enable": req.auto_enable,
        "dry_run": req.dry_run,
        "safety_check": safety_result
    }
    
    if req.dry_run:
        if req.action == "load" and req.plugin_path:
            # Validate plugin without loading
            validation = _validate_plugin_structure(req.plugin_path)
            result.update({
                "status": "would_load",
                "validation": validation,
                "would_enable": req.auto_enable and validation["valid"]
            })
        else:
            result["status"] = f"would_{req.action}"
        
        log_action("/plugins", req.action, req.dict(), result, dry_run=True)
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
    
    try:
        if req.action == "load":
            if not req.plugin_path:
                return _error_response("MISSING_PLUGIN_PATH", "plugin_path required for load action")
            
            # Validate plugin
            validation = _validate_plugin_structure(req.plugin_path)
            if not validation["valid"]:
                return _error_response("INVALID_PLUGIN", f"Plugin validation failed: {', '.join(validation['errors'])}")
            
            # Load plugin module
            plugin_module = _load_plugin_module(req.plugin_path, req.plugin_name)
            
            # Initialize plugin
            init_result = _initialize_plugin(plugin_module, req.plugin_config)
            
            # Register plugin
            plugin_info = {
                "name": req.plugin_name,
                "path": req.plugin_path,
                "module": plugin_module,
                "loaded_at": int(time.time() * 1000),
                "enabled": req.auto_enable,
                "config": req.plugin_config or {},
                "validation": validation,
                "initialization": init_result
            }
            
            _loaded_plugins[req.plugin_name] = plugin_info
            
            result.update({
                "status": "loaded",
                "plugin_info": {
                    "name": plugin_info["name"],
                    "loaded_at": plugin_info["loaded_at"],
                    "enabled": plugin_info["enabled"],
                    "capabilities": validation.get("capabilities", []),
                    "hooks": validation.get("hooks", [])
                }
            })
        
        elif req.action == "unload":
            if req.plugin_name not in _loaded_plugins:
                return _error_response("PLUGIN_NOT_FOUND", f"Plugin '{req.plugin_name}' not loaded")
            
            plugin_info = _loaded_plugins[req.plugin_name]
            
            # Call plugin cleanup if available
            try:
                if hasattr(plugin_info["module"], 'cleanup_plugin'):
                    plugin_info["module"].cleanup_plugin()
                elif hasattr(plugin_info["module"], 'cleanup'):
                    plugin_info["module"].cleanup()
            except Exception as e:
                # Log warning but continue with unload
                pass
            
            # Remove from registry
            del _loaded_plugins[req.plugin_name]
            
            result.update({
                "status": "unloaded",
                "plugin_name": req.plugin_name
            })
        
        elif req.action == "reload":
            # Unload then load
            if req.plugin_name in _loaded_plugins:
                plugin_info = _loaded_plugins[req.plugin_name]
                old_path = plugin_info["path"]
                old_config = plugin_info["config"]
                
                # Unload
                try:
                    if hasattr(plugin_info["module"], 'cleanup_plugin'):
                        plugin_info["module"].cleanup_plugin()
                except:
                    pass
                
                del _loaded_plugins[req.plugin_name]
                
                # Reload
                plugin_path = req.plugin_path or old_path
                plugin_config = req.plugin_config or old_config
                
                plugin_module = _load_plugin_module(plugin_path, req.plugin_name)
                init_result = _initialize_plugin(plugin_module, plugin_config)
                
                new_plugin_info = {
                    "name": req.plugin_name,
                    "path": plugin_path,
                    "module": plugin_module,
                    "loaded_at": int(time.time() * 1000),
                    "enabled": req.auto_enable,
                    "config": plugin_config,
                    "initialization": init_result
                }
                
                _loaded_plugins[req.plugin_name] = new_plugin_info
                
                result.update({
                    "status": "reloaded",
                    "plugin_name": req.plugin_name
                })
            else:
                return _error_response("PLUGIN_NOT_FOUND", f"Plugin '{req.plugin_name}' not loaded for reload")
        
        log_action("/plugins", req.action, req.dict(), result, dry_run=False)
        
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return _error_response("PLUGIN_ERROR", str(e))

@router.post("/capabilities", dependencies=[Depends(verify_key)])
def plugin_capabilities(req: PluginCapabilityRequest, response: Response):
    """
    Query and manage plugin capabilities.
    Lists available features and allows capability control.
    """
    start_time = time.time()
    
    if req.action not in ["list", "query", "enable", "disable"]:
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    result = {
        "action": req.action,
        "plugin_name": req.plugin_name,
        "capability_name": req.capability_name,
        "filters": req.filters
    }
    
    try:
        if req.action == "list":
            # List all capabilities from loaded plugins
            all_capabilities = {}
            
            for plugin_name, plugin_info in _loaded_plugins.items():
                if req.plugin_name and plugin_name != req.plugin_name:
                    continue
                
                capabilities = []
                
                # Get capabilities from validation info
                if "validation" in plugin_info:
                    capabilities.extend(plugin_info["validation"].get("capabilities", []))
                
                # Get capabilities from module
                if hasattr(plugin_info["module"], 'get_capabilities'):
                    try:
                        module_caps = plugin_info["module"].get_capabilities()
                        capabilities.extend(module_caps)
                    except:
                        pass
                
                all_capabilities[plugin_name] = {
                    "capabilities": capabilities,
                    "enabled": plugin_info["enabled"],
                    "loaded_at": plugin_info["loaded_at"]
                }
            
            result.update({
                "status": "listed",
                "plugin_capabilities": all_capabilities,
                "total_plugins": len(all_capabilities),
                "total_capabilities": sum(len(caps["capabilities"]) for caps in all_capabilities.values())
            })
        
        elif req.action == "query":
            if not req.plugin_name:
                return _error_response("MISSING_PLUGIN_NAME", "plugin_name required for query action")
            
            if req.plugin_name not in _loaded_plugins:
                return _error_response("PLUGIN_NOT_FOUND", f"Plugin '{req.plugin_name}' not loaded")
            
            plugin_info = _loaded_plugins[req.plugin_name]
            
            # Query specific capability
            capability_details = {}
            
            if hasattr(plugin_info["module"], 'query_capability') and req.capability_name:
                try:
                    capability_details = plugin_info["module"].query_capability(req.capability_name)
                except:
                    capability_details = {"error": "Capability query failed"}
            
            result.update({
                "status": "queried",
                "plugin_name": req.plugin_name,
                "capability_name": req.capability_name,
                "capability_details": capability_details
            })
        
        elif req.action in ["enable", "disable"]:
            if not req.plugin_name:
                return _error_response("MISSING_PLUGIN_NAME", f"plugin_name required for {req.action} action")
            
            if req.plugin_name not in _loaded_plugins:
                return _error_response("PLUGIN_NOT_FOUND", f"Plugin '{req.plugin_name}' not loaded")
            
            plugin_info = _loaded_plugins[req.plugin_name]
            
            # Enable/disable plugin
            plugin_info["enabled"] = (req.action == "enable")
            
            # Call plugin enable/disable method if available
            try:
                if req.action == "enable" and hasattr(plugin_info["module"], 'enable_plugin'):
                    plugin_info["module"].enable_plugin()
                elif req.action == "disable" and hasattr(plugin_info["module"], 'disable_plugin'):
                    plugin_info["module"].disable_plugin()
            except Exception as e:
                # Continue but note the error
                result["warning"] = f"Plugin {req.action} method failed: {str(e)}"
            
            result.update({
                "status": f"{req.action}d",
                "plugin_name": req.plugin_name,
                "enabled": plugin_info["enabled"]
            })
        
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return _error_response("CAPABILITY_ERROR", str(e))

@router.post("/hooks", dependencies=[Depends(verify_key)])
def plugin_hooks(req: PluginHookRequest, response: Response):
    """
    Manage plugin hooks for event-driven extensibility.
    Allows plugins to register callbacks for system events.
    """
    start_time = time.time()
    
    if req.action not in ["register", "unregister", "trigger", "list"]:
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    result = {
        "action": req.action,
        "hook_name": req.hook_name,
        "plugin_name": req.plugin_name
    }
    
    try:
        if req.action == "register":
            if not req.plugin_name or not req.callback_function:
                return _error_response("MISSING_FIELDS", "plugin_name and callback_function required for register")
            
            if req.plugin_name not in _loaded_plugins:
                return _error_response("PLUGIN_NOT_FOUND", f"Plugin '{req.plugin_name}' not loaded")
            
            plugin_info = _loaded_plugins[req.plugin_name]
            
            # Register hook
            if req.hook_name not in _plugin_hooks:
                _plugin_hooks[req.hook_name] = []
            
            hook_entry = {
                "plugin_name": req.plugin_name,
                "callback_function": req.callback_function,
                "registered_at": int(time.time() * 1000)
            }
            
            _plugin_hooks[req.hook_name].append(hook_entry)
            
            result.update({
                "status": "registered",
                "hook_registered": hook_entry
            })
        
        elif req.action == "unregister":
            if req.hook_name in _plugin_hooks:
                # Remove hooks for specific plugin or all
                if req.plugin_name:
                    _plugin_hooks[req.hook_name] = [
                        hook for hook in _plugin_hooks[req.hook_name]
                        if hook["plugin_name"] != req.plugin_name
                    ]
                else:
                    _plugin_hooks[req.hook_name] = []
                
                result.update({
                    "status": "unregistered",
                    "remaining_hooks": len(_plugin_hooks[req.hook_name])
                })
            else:
                result.update({"status": "hook_not_found"})
        
        elif req.action == "trigger":
            # Trigger all hooks for this hook name
            triggered_hooks = []
            
            if req.hook_name in _plugin_hooks:
                for hook_entry in _plugin_hooks[req.hook_name]:
                    try:
                        plugin_info = _loaded_plugins.get(hook_entry["plugin_name"])
                        if plugin_info and plugin_info["enabled"]:
                            # Call the hook function
                            callback_func = getattr(plugin_info["module"], hook_entry["callback_function"], None)
                            if callback_func:
                                hook_result = callback_func(req.event_data or {})
                                triggered_hooks.append({
                                    "plugin_name": hook_entry["plugin_name"],
                                    "callback_function": hook_entry["callback_function"],
                                    "success": True,
                                    "result": hook_result
                                })
                    except Exception as e:
                        triggered_hooks.append({
                            "plugin_name": hook_entry["plugin_name"],
                            "callback_function": hook_entry["callback_function"],
                            "success": False,
                            "error": str(e)
                        })
            
            result.update({
                "status": "triggered",
                "hooks_triggered": len(triggered_hooks),
                "hook_results": triggered_hooks
            })
        
        elif req.action == "list":
            # List all registered hooks
            hook_summary = {}
            for hook_name, hooks in _plugin_hooks.items():
                hook_summary[hook_name] = [
                    {
                        "plugin_name": hook["plugin_name"],
                        "callback_function": hook["callback_function"],
                        "registered_at": hook["registered_at"]
                    }
                    for hook in hooks
                ]
            
            result.update({
                "status": "listed",
                "hooks": hook_summary,
                "total_hooks": sum(len(hooks) for hooks in _plugin_hooks.values())
            })
        
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return _error_response("HOOK_ERROR", str(e))

@router.get("/list", dependencies=[Depends(verify_key)])
def list_plugins():
    """List all loaded plugins with status and capabilities"""
    
    plugins_list = []
    
    for plugin_name, plugin_info in _loaded_plugins.items():
        plugin_summary = {
            "name": plugin_name,
            "path": plugin_info["path"],
            "loaded_at": plugin_info["loaded_at"],
            "enabled": plugin_info["enabled"],
            "capabilities": plugin_info.get("validation", {}).get("capabilities", []),
            "hooks": plugin_info.get("validation", {}).get("hooks", []),
            "version": plugin_info.get("validation", {}).get("version"),
            "description": plugin_info.get("validation", {}).get("description")
        }
        plugins_list.append(plugin_summary)
    
    return {
        "result": {
            "plugins": plugins_list,
            "total_loaded": len(plugins_list),
            "total_enabled": sum(1 for p in plugins_list if p["enabled"]),
            "total_capabilities": sum(len(p["capabilities"]) for p in plugins_list),
            "total_hooks": sum(len(p["hooks"]) for p in plugins_list)
        },
        "timestamp": int(time.time() * 1000)
    }

@router.get("/capabilities", dependencies=[Depends(verify_key)])
def get_plugin_system_capabilities():
    """Get plugin system capabilities and limits"""
    capabilities = {
        "plugin_loading": {
            "dynamic_loading": True,
            "hot_reload": True,
            "dependency_management": False,  # Future enhancement
            "sandboxing": False,             # Future enhancement
            "supported_languages": ["python"]
        },
        "capability_management": {
            "capability_discovery": True,
            "capability_enablement": True,
            "capability_querying": True,
            "runtime_reconfiguration": True
        },
        "hook_system": {
            "event_hooks": True,
            "callback_registration": True,
            "hook_chaining": True,
            "async_hooks": False  # Future enhancement
        },
        "plugin_types": {
            "gui_backends": True,      # New GUI libraries
            "input_methods": True,     # Custom input devices
            "screen_readers": True,    # Screen analysis tools
            "automation_workflows": True,  # Custom automation logic
            "integrations": True       # External system integrations
        },
        "limits": {
            "max_loaded_plugins": 50,
            "max_hooks_per_event": 20,
            "plugin_timeout_seconds": 30,
            "max_plugin_memory_mb": 100
        }
    }
    
    return {
        "result": capabilities,
        "timestamp": int(time.time() * 1000)
    }