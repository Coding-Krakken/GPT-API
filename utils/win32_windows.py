import platform
import ctypes
import ctypes.wintypes

def list_windows():
    # Returns a list of dicts: {"hwnd": hwnd, "title": title, "pid": pid}
    windows = []
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    EnumWindows = user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    GetWindowTextW = user32.GetWindowTextW
    GetWindowTextLengthW = user32.GetWindowTextLengthW
    IsWindowVisible = user32.IsWindowVisible
    GetWindowThreadProcessId = user32.GetWindowThreadProcessId

    def foreach_window(hwnd, lParam):
        if IsWindowVisible(hwnd):
            length = GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value
            if title:
                pid = ctypes.wintypes.DWORD()
                GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                windows.append({"hwnd": hwnd, "title": title, "pid": pid.value})
        return True

    EnumWindows(EnumWindowsProc(foreach_window), 0)
    return windows

def focus_window(hwnd):
    user32 = ctypes.windll.user32
    user32.SetForegroundWindow(hwnd)

def minimize_window(hwnd):
    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE

def maximize_window(hwnd):
    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
