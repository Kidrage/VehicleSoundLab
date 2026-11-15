"""Follow one actual Windows process handle; a stale JSON is not liveness."""
import ctypes,json,time
from ctypes import wintypes
from research_archive_v1 import load


class Follow:
    def __init__(self,path,pid=None):
        self.path=path;self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        k=self.kernel;k.OpenProcess.argtypes=(wintypes.DWORD,wintypes.BOOL,wintypes.DWORD);k.OpenProcess.restype=wintypes.HANDLE
        k.GetExitCodeProcess.argtypes=(wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD));k.GetExitCodeProcess.restype=wintypes.BOOL
        k.CloseHandle.argtypes=(wintypes.HANDLE,);k.CloseHandle.restype=wintypes.BOOL
        self.handle=k.OpenProcess(0x1000,False,pid) if pid else None

    def alive(self):
        if not self.handle:return False
        code=wintypes.DWORD()
        if not self.kernel.GetExitCodeProcess(self.handle,ctypes.byref(code)):raise ctypes.WinError(ctypes.get_last_error())
        return code.value==259

    def read(self):
        while True:
            try:return load(self.path)
            except (FileNotFoundError,json.JSONDecodeError):
                if not self.alive():raise
                time.sleep(.2)

    def case(self,index):
        while True:
            record=self.read()
            if len(record['cases'])>index:return record,record['cases'][index]
            if not self.alive():
                record=self.read()
                if len(record['cases'])>index:return record,record['cases'][index]
                raise RuntimeError('Producer terminal before expected source')
            time.sleep(.25)

    def close(self):
        if self.handle:self.kernel.CloseHandle(self.handle);self.handle=None
