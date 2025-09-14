"""
Asynchronous GUI detection to avoid blocking FastAPI event loop
"""

import asyncio
import time
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor
from utils.gui_env import detect_gui_environment_comprehensive


# Thread pool for blocking operations
_gui_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="gui_detector")

# Cache for GUI session data
_async_gui_cache = {"data": None, "timestamp": 0, "loading": False}
_cache_ttl = 30  # 30 seconds


async def get_gui_session_async() -> Dict[str, Any]:
    """
    Get GUI session information asynchronously with caching
    """
    current_time = time.time()
    
    # Check if we have fresh cached data
    if (_async_gui_cache["data"] is not None and 
        current_time - _async_gui_cache["timestamp"] < _cache_ttl and
        not _async_gui_cache["loading"]):
        return _async_gui_cache["data"]
    
    # If already loading, return cached data or wait briefly
    if _async_gui_cache["loading"]:
        if _async_gui_cache["data"] is not None:
            return _async_gui_cache["data"]
        # Wait a short time for the loading to complete
        await asyncio.sleep(0.1)
        if _async_gui_cache["data"] is not None:
            return _async_gui_cache["data"]
    
    # Start loading
    _async_gui_cache["loading"] = True
    
    try:
        # Run the blocking GUI detection in a thread pool
        loop = asyncio.get_event_loop()
        gui_data = await loop.run_in_executor(
            _gui_executor, 
            detect_gui_environment_comprehensive
        )
        
        # Update cache
        _async_gui_cache["data"] = gui_data
        _async_gui_cache["timestamp"] = current_time
        
        return gui_data
        
    finally:
        _async_gui_cache["loading"] = False


async def clear_gui_cache():
    """Clear the GUI detection cache to force fresh detection"""
    _async_gui_cache["data"] = None
    _async_gui_cache["timestamp"] = 0
    _async_gui_cache["loading"] = False