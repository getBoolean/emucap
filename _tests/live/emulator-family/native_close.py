"""Windows-only native window-close probe for the exact owned emulator process."""
import ctypes as c
from ctypes import wintypes as w
import os


def owned_windows(user, pid):
    callback_type = c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    user.EnumWindows.argtypes = [callback_type, w.LPARAM]
    user.IsWindowVisible.argtypes = [w.HWND]
    user.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
    windows = []

    @callback_type
    def collect(window, _):
        owner = w.DWORD()
        user.GetWindowThreadProcessId(window, c.byref(owner))
        if owner.value == pid:
            windows.append((window, bool(user.IsWindowVisible(window))))
        return True

    if not user.EnumWindows(collect, 0):
        raise c.WinError(c.get_last_error())
    return windows


def verify_visibility(pid, display):
    if os.name != 'nt':
        raise RuntimeError('native visibility qualification requires Windows')
    windows = owned_windows(c.WinDLL('user32', use_last_error=True), pid)
    visible = sum(shown for _, shown in windows)
    if not windows or bool(visible) != display:
        raise RuntimeError(f'native window visibility differs from display={display}: {visible}/{len(windows)}')
    return {'owned_windows': len(windows), 'visible_windows': visible, 'requested_display': display}


def close_owned_window(pid, timeout_ms=20000):
    if os.name != 'nt':
        raise RuntimeError('native window-close qualification requires Windows')
    kernel = c.WinDLL('kernel32', use_last_error=True)
    user = c.WinDLL('user32', use_last_error=True)
    kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    kernel.OpenProcess.restype = w.HANDLE
    kernel.GetExitCodeProcess.argtypes = [w.HANDLE, c.POINTER(w.DWORD)]
    kernel.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
    kernel.WaitForSingleObject.restype = w.DWORD
    kernel.CloseHandle.argtypes = [w.HANDLE]
    user.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
    handle = kernel.OpenProcess(0x100000 | 0x1000, False, pid)
    if not handle:
        raise c.WinError(c.get_last_error())
    try:
        code = w.DWORD()

        def require_alive():
            if not kernel.GetExitCodeProcess(handle, c.byref(code)):
                raise c.WinError(c.get_last_error())
            if code.value != 259:
                raise RuntimeError(f'owned emulator already exited: {code.value}')

        require_alive()
        windows = [window for window, visible in owned_windows(user, pid) if visible]
        if len(windows) != 1:
            raise RuntimeError(f'expected exactly one visible owned emulator window, found {len(windows)}')
        require_alive()
        if not user.PostMessageW(windows[0], 0x0010, 0, 0):  # WM_CLOSE
            raise c.WinError(c.get_last_error())
        wait = kernel.WaitForSingleObject(handle, timeout_ms)
        if wait != 0:
            raise RuntimeError(f'native close did not terminate the owned emulator: wait={wait}')
        if not kernel.GetExitCodeProcess(handle, c.byref(code)):
            raise c.WinError(c.get_last_error())
        if code.value != 0:
            raise RuntimeError(f'native close exited abnormally: {code.value}')
        return {'method': 'owned-window-WM_CLOSE', 'exit_code': code.value, 'process_exited': True}
    finally:
        kernel.CloseHandle(handle)
