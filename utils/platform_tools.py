import os
import platform
import shlex

WINDOWS_ALIASES = {
    'ls': 'dir',
    'cat': 'type',
    'pwd': 'cd',
    'clear': 'cls',
    'cp': 'copy',
    'mv': 'move',
    'rm': 'del',
    'ps': 'tasklist',
    'kill': 'taskkill',
    'grep': 'findstr',
    'which': 'where',
}

def is_windows():
    return os.name == 'nt' or platform.system().lower() == 'windows'

def normalize_path(path):
    # Normalize path for current OS, handle drive letters and slashes
    if is_windows():
        # Expand ~ and environment variables
        path = os.path.expandvars(os.path.expanduser(path))
        # Convert / to \
        path = os.path.normpath(path)
        # Handle drive letter normalization
        if len(path) > 2 and path[1] == ':' and path[2] != '\\':
            path = path[:2] + '\\' + path[2:]
        return path
    else:
        return os.path.expanduser(path)
def get_encoding():
    return "cp1252" if is_windows() else "utf-8"

def background_command(cmd):
    # Returns a command string to run in background for the current OS
    if is_windows():
        # Use start for background in cmd, Start-Process for PowerShell
        return f'start /B {cmd}'
    else:
        return f'{cmd} &'

def translate_command_for_windows(command):
    # Only replace the first word if it's an alias
    parts = shlex.split(command, posix=not is_windows())
    if not parts:
        return command
    alias = WINDOWS_ALIASES.get(parts[0].lower())
    if alias:
        parts[0] = alias
        return ' '.join(parts)
    return command
