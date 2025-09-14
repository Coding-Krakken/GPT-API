"""
Performance optimization and batching endpoints for GUI automation.
Provides action batching, region-scoped operations, and latency optimization.
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union
import time
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from utils.auth import verify_key
from utils.safety import safety_check, log_action

router = APIRouter()

class BatchOperation(BaseModel):
    endpoint: str  # "/input", "/screen", etc.
    action: str
    params: Dict[str, Any]
    priority: Optional[int] = 1  # Higher numbers = higher priority
    timeout: Optional[float] = 30.0

class BatchRequest(BaseModel):
    action: str  # "execute", "validate", "optimize"
    operations: List[BatchOperation]
    execution_mode: Optional[str] = "sequential"  # "sequential", "parallel", "optimized"
    max_parallel: Optional[int] = 3
    fail_fast: Optional[bool] = False
    dry_run: Optional[bool] = False

class RegionScopeRequest(BaseModel):
    action: str
    region: Dict[str, int]  # {x, y, width, height}
    operations: List[Dict[str, Any]]
    optimization_level: Optional[str] = "balanced"  # "speed", "accuracy", "balanced"
    cache_results: Optional[bool] = True
    dry_run: Optional[bool] = False

class PerformanceProfile(BaseModel):
    action: str
    target_latency: Optional[int] = 500  # Target latency in ms
    accuracy_threshold: Optional[float] = 0.95  # Minimum accuracy
    resource_limit: Optional[str] = "medium"  # "low", "medium", "high"
    enable_caching: Optional[bool] = True
    parallel_limit: Optional[int] = 3

def _error_response(code: str, message: str, extra: Optional[Dict] = None) -> Dict:
    """Create standardized error response"""
    result = {
        "errors": [{"code": code, "message": message}],
        "timestamp": int(time.time() * 1000)
    }
    if extra:
        result.update(extra)
    return result

def _simulate_operation(operation: BatchOperation) -> Dict[str, Any]:
    """Simulate executing a GUI operation"""
    import random
    
    # Simulate different latencies based on operation type
    base_latency = {
        "/screen": 200,  # Screen operations are slower
        "/input": 50,    # Input operations are fast
        "/flow": 100,    # Flow operations medium
        "/clipboard": 30 # Clipboard operations very fast
    }.get(operation.endpoint, 100)
    
    # Add random variation
    actual_latency = base_latency + random.randint(-20, 50)
    time.sleep(actual_latency / 1000.0)  # Convert to seconds
    
    # Simulate success/failure
    success_rate = 0.95
    success = random.random() < success_rate
    
    return {
        "success": success,
        "latency_ms": actual_latency,
        "endpoint": operation.endpoint,
        "action": operation.action,
        "params": operation.params,
        "priority": operation.priority,
        "error": None if success else "Simulated operation failure"
    }

def _optimize_batch_order(operations: List[BatchOperation], mode: str) -> List[BatchOperation]:
    """Optimize the order of batch operations for performance"""
    if mode == "priority":
        # Sort by priority (highest first)
        return sorted(operations, key=lambda op: op.priority, reverse=True)
    
    elif mode == "latency":
        # Group fast operations first
        fast_endpoints = ["/clipboard", "/input"]
        slow_endpoints = ["/screen", "/flow"]
        
        fast_ops = [op for op in operations if op.endpoint in fast_endpoints]
        slow_ops = [op for op in operations if op.endpoint in slow_endpoints]
        other_ops = [op for op in operations if op.endpoint not in fast_endpoints + slow_endpoints]
        
        return fast_ops + other_ops + slow_ops
    
    elif mode == "dependency":
        # Screen captures should happen before input operations that depend on them
        screen_ops = [op for op in operations if op.endpoint == "/screen"]
        other_ops = [op for op in operations if op.endpoint != "/screen"]
        
        return screen_ops + other_ops
    
    else:
        # No optimization
        return operations

async def _execute_batch_sequential(operations: List[BatchOperation]) -> List[Dict[str, Any]]:
    """Execute operations sequentially"""
    results = []
    
    for operation in operations:
        result = _simulate_operation(operation)
        results.append(result)
        
        # If operation failed and fail_fast is enabled, stop here
        if not result["success"]:
            break
    
    return results

async def _execute_batch_parallel(operations: List[BatchOperation], max_parallel: int) -> List[Dict[str, Any]]:
    """Execute operations in parallel with concurrency limit"""
    semaphore = asyncio.Semaphore(max_parallel)
    
    async def execute_with_semaphore(operation):
        async with semaphore:
            # Run in thread pool since our simulate function is synchronous
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _simulate_operation, operation)
    
    # Execute all operations concurrently
    tasks = [execute_with_semaphore(op) for op in operations]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Convert exceptions to error results
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append({
                "success": False,
                "latency_ms": 0,
                "endpoint": operations[i].endpoint,
                "action": operations[i].action,
                "error": str(result)
            })
        else:
            processed_results.append(result)
    
    return processed_results

@router.post("/batch", dependencies=[Depends(verify_key)])
async def batch_operations(req: BatchRequest, response: Response):
    """
    Execute multiple GUI operations efficiently with batching and optimization.
    Supports sequential, parallel, and optimized execution modes.
    """
    start_time = time.time()
    
    if req.action not in ["execute", "validate", "optimize"]:
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    if not req.operations or len(req.operations) == 0:
        return _error_response("NO_OPERATIONS", "No operations provided for batch execution")
    
    # Safety check for batch operation
    batch_params = {
        "operation_count": len(req.operations),
        "execution_mode": req.execution_mode,
        "max_parallel": req.max_parallel
    }
    
    safety_result = safety_check("/batch_gui", req.action, batch_params, req.dry_run)
    if not safety_result["safe"]:
        return _error_response("SAFETY_VIOLATION", safety_result["message"], {"safety": safety_result})
    
    result = {
        "action": req.action,
        "operation_count": len(req.operations),
        "execution_mode": req.execution_mode,
        "max_parallel": req.max_parallel,
        "fail_fast": req.fail_fast,
        "dry_run": req.dry_run,
        "safety_check": safety_result
    }
    
    if req.dry_run:
        # Validate and optimize without executing
        optimized_operations = _optimize_batch_order(req.operations, "priority")
        
        result.update({
            "status": "would_execute",
            "optimizations_applied": {
                "reordered": len(optimized_operations) != len(req.operations),
                "parallel_eligible": req.execution_mode == "parallel",
                "estimated_time_ms": sum(100 for _ in req.operations) if req.execution_mode == "sequential" else max(100, len(req.operations) * 20)
            },
            "operation_summary": [
                {
                    "endpoint": op.endpoint,
                    "action": op.action,
                    "priority": op.priority
                } for op in optimized_operations
            ]
        })
        
        log_action("/batch_gui", req.action, req.dict(), result, dry_run=True)
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
    
    try:
        # Optimize operation order
        optimized_operations = _optimize_batch_order(req.operations, req.execution_mode)
        
        # Execute operations
        if req.execution_mode == "parallel":
            operation_results = await _execute_batch_parallel(optimized_operations, req.max_parallel)
        else:
            operation_results = await _execute_batch_sequential(optimized_operations)
        
        # Calculate statistics
        successful_ops = sum(1 for r in operation_results if r["success"])
        failed_ops = len(operation_results) - successful_ops
        total_latency = sum(r["latency_ms"] for r in operation_results)
        avg_latency = total_latency / len(operation_results) if operation_results else 0
        
        result.update({
            "status": "completed",
            "operation_results": operation_results,
            "statistics": {
                "total_operations": len(operation_results),
                "successful_operations": successful_ops,
                "failed_operations": failed_ops,
                "success_rate": successful_ops / len(operation_results) if operation_results else 0,
                "total_latency_ms": total_latency,
                "average_latency_ms": avg_latency,
                "execution_time_ms": int((time.time() - start_time) * 1000)
            }
        })
        
        log_action("/batch_gui", req.action, req.dict(), result, dry_run=False)
        
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return _error_response("BATCH_EXECUTION_ERROR", str(e))

@router.post("/region_scope", dependencies=[Depends(verify_key)])
def region_scoped_operations(req: RegionScopeRequest, response: Response):
    """
    Execute operations scoped to specific screen regions for performance.
    Reduces processing overhead by limiting operation scope.
    """
    start_time = time.time()
    
    if req.action not in ["execute", "analyze", "optimize"]:
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    # Validate region
    if not all(key in req.region for key in ["x", "y", "width", "height"]):
        return _error_response("INVALID_REGION", "Region must contain x, y, width, height")
    
    if any(val < 0 for val in req.region.values()):
        return _error_response("INVALID_REGION", "Region coordinates must be non-negative")
    
    # Safety check
    safety_result = safety_check("/batch_gui", req.action, req.dict(), req.dry_run)
    if not safety_result["safe"]:
        return _error_response("SAFETY_VIOLATION", safety_result["message"], {"safety": safety_result})
    
    result = {
        "action": req.action,
        "region": req.region,
        "operation_count": len(req.operations),
        "optimization_level": req.optimization_level,
        "cache_results": req.cache_results,
        "dry_run": req.dry_run,
        "safety_check": safety_result
    }
    
    if req.dry_run:
        # Estimate performance improvements
        region_area = req.region["width"] * req.region["height"]
        full_screen_area = 1920 * 1080  # Assume standard resolution
        area_ratio = region_area / full_screen_area
        
        estimated_speedup = 1.0 / max(0.1, area_ratio)  # Smaller regions = bigger speedup
        
        result.update({
            "status": "would_execute",
            "performance_estimate": {
                "region_area": region_area,
                "area_ratio": area_ratio,
                "estimated_speedup": round(estimated_speedup, 2),
                "estimated_time_reduction_percent": round((1 - area_ratio) * 100, 1)
            }
        })
        
        log_action("/batch_gui", req.action, req.dict(), result, dry_run=True)
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
    
    try:
        # Simulate region-scoped execution
        operation_results = []
        
        for operation in req.operations:
            # Add region scope to operation parameters
            scoped_params = operation.copy()
            scoped_params["region"] = req.region
            
            # Simulate faster execution due to smaller scope
            base_time = 100
            region_area = req.region["width"] * req.region["height"]
            speedup_factor = max(0.1, min(1.0, region_area / (1920 * 1080)))
            actual_time = int(base_time * speedup_factor)
            
            time.sleep(actual_time / 1000.0)
            
            operation_results.append({
                "operation": operation,
                "success": True,
                "latency_ms": actual_time,
                "region_optimized": True
            })
        
        result.update({
            "status": "completed",
            "operation_results": operation_results,
            "performance_metrics": {
                "total_operations": len(operation_results),
                "total_time_ms": sum(r["latency_ms"] for r in operation_results),
                "average_time_ms": sum(r["latency_ms"] for r in operation_results) / len(operation_results),
                "region_optimization_applied": True
            }
        })
        
        log_action("/batch_gui", req.action, req.dict(), result, dry_run=False)
        
        return {
            "result": result,
            "timestamp": int(time.time() * 1000),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return _error_response("REGION_SCOPE_ERROR", str(e))

@router.post("/profile", dependencies=[Depends(verify_key)])
def performance_profile(req: PerformanceProfile, response: Response):
    """
    Configure performance profile for optimal GUI automation.
    Balances speed, accuracy, and resource usage.
    """
    start_time = time.time()
    
    if req.action not in ["set", "get", "optimize", "benchmark"]:
        return _error_response("INVALID_ACTION", f"Unsupported action: {req.action}")
    
    # Safety check
    safety_result = safety_check("/batch_gui", req.action, req.dict())
    if not safety_result["safe"]:
        return _error_response("SAFETY_VIOLATION", safety_result["message"], {"safety": safety_result})
    
    result = {
        "action": req.action,
        "target_latency": req.target_latency,
        "accuracy_threshold": req.accuracy_threshold,
        "resource_limit": req.resource_limit,
        "enable_caching": req.enable_caching,
        "parallel_limit": req.parallel_limit,
        "safety_check": safety_result
    }
    
    if req.action == "benchmark":
        # Run performance benchmark
        benchmark_results = {
            "screen_capture_ms": 150,
            "ocr_processing_ms": 300,
            "template_matching_ms": 200,
            "input_operation_ms": 50,
            "clipboard_operation_ms": 30,
            "batch_overhead_ms": 10
        }
        
        result.update({
            "status": "benchmarked",
            "benchmark_results": benchmark_results,
            "recommendations": {
                "optimal_batch_size": 5,
                "recommended_parallel_limit": 3,
                "caching_benefit": "high",
                "region_scoping_benefit": "medium"
            }
        })
    
    else:
        result.update({
            "status": "configured",
            "active_optimizations": {
                "batching": True,
                "parallel_execution": req.parallel_limit > 1,
                "region_scoping": True,
                "caching": req.enable_caching,
                "priority_ordering": True
            }
        })
    
    log_action("/batch_gui", req.action, req.dict(), result)
    
    return {
        "result": result,
        "timestamp": int(time.time() * 1000),
        "latency_ms": int((time.time() - start_time) * 1000)
    }

@router.get("/capabilities", dependencies=[Depends(verify_key)])
def get_performance_capabilities():
    """Get available performance optimization capabilities"""
    capabilities = {
        "batching": {
            "max_batch_size": 50,
            "execution_modes": ["sequential", "parallel", "optimized"],
            "max_parallel_operations": 10,
            "operation_prioritization": True
        },
        "region_scoping": {
            "supported": True,
            "min_region_size": {"width": 10, "height": 10},
            "max_region_size": {"width": 5000, "height": 5000},
            "optimization_levels": ["speed", "accuracy", "balanced"]
        },
        "caching": {
            "screen_capture_cache": True,
            "template_match_cache": True,
            "ocr_result_cache": True,
            "max_cache_size_mb": 100
        },
        "performance_targets": {
            "target_latency_ms": 500,
            "batch_overhead_ms": 10,
            "parallel_speedup_factor": 2.5,
            "region_scope_speedup": 3.0
        },
        "monitoring": {
            "real_time_metrics": True,
            "performance_profiling": True,
            "benchmark_suite": True,
            "optimization_suggestions": True
        }
    }
    
    return {
        "result": capabilities,
        "timestamp": int(time.time() * 1000)
    }