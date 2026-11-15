"""Retain the original Windows process object rather than repeatedly trust PID."""
import ctypes
from ctypes import wintypes


class OriginalProcess:
    def __init__(self, pid):
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        self.kernel.GetExitCodeProcess.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.pid = int(pid)
        self.handle = self.kernel.OpenProcess(0x1000, False, self.pid)
        self.initial_error = ctypes.get_last_error() if not self.handle else 0

    def state(self):
        if not self.handle:
            return dict(pid=self.pid, process_handle_available=False, live=False,
                        open_error=self.initial_error, exit_code=None)
        code = wintypes.DWORD()
        if not self.kernel.GetExitCodeProcess(self.handle, ctypes.byref(code)):
            raise OSError(ctypes.get_last_error(), 'Cannot query retained original process handle')
        return dict(pid=self.pid, process_handle_available=True, live=code.value == 259,
                    open_error=0, exit_code=None if code.value == 259 else int(code.value))

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
