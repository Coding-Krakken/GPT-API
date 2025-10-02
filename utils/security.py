"""
Security utilities for safe command execution and input validation
"""

import re
import shlex
import subprocess
import os
from typing import List, Optional, Dict, Any
from pathlib import Path


class CommandSanitizer:
    """Sanitizes and validates shell commands to prevent injection attacks"""
    
    # Allow-list of safe commands for GUI operations
    ALLOWED_GUI_COMMANDS = {
        'wmctrl', 'xprop', 'xwininfo', 'xdotool', 'swaymsg', 'wlr-randr', 
        'wayland-info', 'xdg-desktop-portal-kde', 'xdg-desktop-portal-gnome',
        'xdg-desktop-portal-wlr', 'Xvfb', 'vncserver', 'x11vnc', 'scrot',
        'gnome-screenshot', 'spectacle', 'xvkbd', 'ydotool', 'at-spi2-core',
        'accerciser', 'ps', 'pgrep', 'pkill', 'which', 'echo', 'test'
    }
    
    # Pattern for safe arguments (alphanumeric, common symbols, paths)
    SAFE_ARG_PATTERN = re.compile(r'^[a-zA-Z0-9\-_./:\s=,@+]*$')
    
    @classmethod
    def sanitize_command(cls, command: str) -> List[str]:
        """
        Safely parse and validate a shell command.
        Returns a list suitable for subprocess without shell=True
        """
        if not command or not command.strip():
            raise ValueError("Empty command not allowed")
            
        try:
            # Parse the command safely
            parts = shlex.split(command.strip())
        except ValueError as e:
            raise ValueError(f"Invalid command syntax: {e}")
            
        if not parts:
            raise ValueError("No command found after parsing")
            
        base_command = parts[0]
        
        # Extract just the command name without path
        command_name = os.path.basename(base_command)
        
        # Check if command is in allow-list
        if command_name not in cls.ALLOWED_GUI_COMMANDS:
            raise ValueError(f"Command '{command_name}' not in allow-list")
            
        # Validate all arguments
        for arg in parts[1:]:
            if not cls.SAFE_ARG_PATTERN.match(arg):
                raise ValueError(f"Unsafe argument detected: {arg}")
                
        return parts
    
    @classmethod
    def validate_path(cls, path: str) -> str:
        """Validate and sanitize file paths"""
        if not path:
            raise ValueError("Empty path not allowed")
            
        # Resolve path and check for directory traversal
        try:
            resolved_path = os.path.abspath(path)
            # Ensure path doesn't escape current working directory or common safe areas
            safe_roots = ['/tmp', '/var/tmp', os.getcwd(), '/home']
            if not any(resolved_path.startswith(root) for root in safe_roots):
                raise ValueError(f"Path outside allowed directories: {resolved_path}")
            return resolved_path
        except Exception as e:
            raise ValueError(f"Invalid path: {e}")


def safe_subprocess_run(command: str, timeout: int = 10, cwd: Optional[str] = None) -> Dict[str, Any]:
    """
    Safely execute a command without shell=True
    """
    start_time = int(subprocess.run(['date', '+%s%6N'], capture_output=True, text=True).stdout.strip() or '0')
    
    result = {
        "timestamp": start_time,
        "stdout": "",
        "stderr": "", 
        "exit_code": -1,
        "latency_us": 0,
        "error": None,
        "command": command
    }
    
    try:
        # Sanitize the command
        cmd_parts = CommandSanitizer.sanitize_command(command)
        
        # Execute safely without shell=True
        proc = subprocess.run(
            cmd_parts,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd
        )
        
        end_time = int(subprocess.run(['date', '+%s%6N'], capture_output=True, text=True).stdout.strip() or str(start_time))
        
        result.update({
            "stdout": proc.stdout.strip() if proc.stdout else "",
            "stderr": proc.stderr.strip() if proc.stderr else "",
            "exit_code": proc.returncode,
            "latency_us": end_time - start_time
        })
        
    except ValueError as e:
        # Command validation failed
        result["error"] = f"Security validation failed: {str(e)}"
        result["exit_code"] = -2
    except subprocess.TimeoutExpired:
        result["error"] = f"Command timed out after {timeout}s"
        result["exit_code"] = -3
    except FileNotFoundError:
        result["error"] = f"Command not found: {cmd_parts[0] if cmd_parts else command}"
        result["exit_code"] = -4  
    except Exception as e:
        result["error"] = f"Execution failed: {str(e)}"
        result["exit_code"] = -5
    
    return result


def safe_popen(command: str, **kwargs) -> subprocess.Popen:
    """
    Safely create a Popen process without shell=True
    """
    try:
        cmd_parts = CommandSanitizer.sanitize_command(command)
        # Remove shell=True from kwargs if present
        kwargs.pop('shell', None)
        return subprocess.Popen(cmd_parts, **kwargs)
    except ValueError as e:
        raise ValueError(f"Security validation failed: {str(e)}")