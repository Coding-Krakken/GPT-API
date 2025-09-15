from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import time
import traceback
import os
from routes import (
    shell, files, code, system, monitor, git, package, apps, refactor, batch, 
    screen, input, safety, session, flow, clipboard, batch_gui, debug, plugins,
    orchestrator, universal_driver, ai_planner, workflow_editor, reliability
)
from routes.gui_control import gui_router, apps_router as enhanced_apps_router, input_router as enhanced_input_router, vision_router

load_dotenv()

app = FastAPI(
    title="State-of-the-Art GUI Automation API",
    description="Advanced GUI automation system with AI planning, universal drivers, and live orchestration",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Exception handler for better 500 error observability
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler to provide consistent error format with observability data.
    """
    current_time = time.time()
    timestamp = int(current_time * 1000)
    
    # Determine if this is an HTTPException or internal server error
    if isinstance(exc, HTTPException):
        status_code = exc.status_code
        error_code = f"http_{status_code}"
        message = str(exc.detail)
    else:
        status_code = 500
        error_code = "internal_server_error"
        message = "An internal server error occurred"
    
    # For 500 errors, include additional debugging information
    error_detail = {
        "error": {
            "code": error_code,
            "message": message
        },
        "status": status_code,
        "timestamp": timestamp,
        "path": str(request.url.path),
        "method": request.method
    }
    
    # For 500 errors, include debugging info only in development
    if status_code == 500:
        # Only include stack traces in development mode
        debug_mode = os.getenv('DEBUG', 'false').lower() == 'true'
        
        if debug_mode:
            error_detail["error"]["traceback"] = traceback.format_exc()
            error_detail["error"]["exception_type"] = type(exc).__name__
            # Log the error for server-side debugging
            print(f"Internal Server Error at {request.url.path}: {exc}")
            print(traceback.format_exc())
        else:
            # Production mode - sanitized error info only
            error_detail["error"]["exception_type"] = type(exc).__name__
            # Log sanitized version without exposing stack trace to response
            print(f"Internal Server Error at {request.url.path}: {type(exc).__name__}")
    
    return JSONResponse(
        status_code=status_code,
        content=error_detail
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core Backend Routes
app.include_router(shell.router, prefix="/shell")
app.include_router(files.router, prefix="/files")
app.include_router(files.router, prefix="/manageFiles")  # Alias for tool compatibility
app.include_router(code.router, prefix="/code")
app.include_router(system.router, prefix="/system")
app.include_router(monitor.router, prefix="/monitor")
app.include_router(git.router, prefix="/git")
app.include_router(package.router, prefix="/package")
app.include_router(apps.router, prefix="/apps")
app.include_router(refactor.router, prefix="/refactor")
app.include_router(batch.router, prefix="/batch")

# Advanced GUI Automation Routes
app.include_router(screen.router, prefix="/screen")
app.include_router(input.router, prefix="/input")
app.include_router(safety.router, prefix="/safety")
app.include_router(session.router, prefix="/session")
app.include_router(flow.router, prefix="/flow")
app.include_router(clipboard.router, prefix="/clipboard")

# Enhanced GUI Control Layer (New Implementation)
app.include_router(gui_router, prefix="/gui")
app.include_router(enhanced_apps_router, prefix="/apps_advanced")  # Enhanced apps endpoints
app.include_router(enhanced_input_router, prefix="/input_enhanced") 
app.include_router(vision_router, prefix="/vision")

# Performance & Developer Tools
app.include_router(batch_gui.router, prefix="/batch_gui")
app.include_router(debug.router, prefix="/debug")
app.include_router(plugins.router, prefix="/plugins")

# State-of-the-Art Features
app.include_router(orchestrator.router, prefix="/orchestrator")
app.include_router(universal_driver.router, prefix="/universal_driver")
app.include_router(ai_planner.router, prefix="/ai_planner")
app.include_router(workflow_editor.router, prefix="/workflow_editor")
app.include_router(reliability.router, prefix="/reliability")

@app.get("/")
def root():
    return {
        "system": "State-of-the-Art GUI Automation API",
        "version": "2.0.0",
        "features": [
            "Live Orchestration & Bi-directional Bridge",
            "Universal Multi-platform GUI Driver",
            "AI-driven Task Planning & Autonomous Mode",
            "Enterprise Safety & Governance",
            "Virtual DOM Overlays for Web",
            "Cross-platform Native APIs",
            "Real-time Streaming Dashboards",
            "Adaptive Interaction Intelligence",
            "Visual Workflow Editor & Declarative Schemas",
            "Advanced Reliability & Circuit Breakers",
            "Chaos Engineering & Resilience Testing"
        ],
        "endpoints": "/docs",
        "total_routes": len(app.routes),
        "advanced_capabilities": True
    }

@app.get("/debug/routes")
def list_routes():
    return [r.path for r in app.routes]

@app.get("/system/capabilities")
def system_capabilities():
    """Get comprehensive system capabilities overview"""
    return {
        "core_backend": {
            "shell_operations": True,
            "file_management": True,
            "code_execution": True,
            "system_monitoring": True,
            "git_integration": True,
            "package_management": True,
            "app_control": True
        },
        "gui_automation": {
            "screen_perception": True,
            "advanced_input_synthesis": True,
            "safety_governance": True,
            "remote_sessions": True,
            "flow_control": True,
            "clipboard_operations": True,
            "performance_optimization": True,
            "debugging_tools": True,
            "plugin_system": True
        },
        "state_of_the_art": {
            "live_orchestration": True,
            "bi_directional_bridge": True,
            "universal_driver": True,
            "ai_task_planning": True,
            "autonomous_execution": True,
            "virtual_dom_overlay": True,
            "adaptive_intelligence": True,
            "real_time_streaming": True,
            "visual_workflow_editor": True,
            "declarative_schemas": True,
            "advanced_reliability": True,
            "chaos_engineering": True
        },
        "enterprise_features": {
            "comprehensive_safety": True,
            "audit_logging": True,
            "role_based_access": False,  # Future enhancement
            "compliance_reporting": False,  # Future enhancement
            "enterprise_sso": False  # Future enhancement
        },
        "platforms_supported": ["Windows", "Linux", "macOS", "Web", "Mobile"],
        "total_endpoints": len(app.routes),
        "api_version": "2.0.0"
    }
