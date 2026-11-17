"""Windows float32 output only. The device owns no synthesis or control state."""
import ctypes as C
from ctypes import wintypes as W
import time


class Format(C.Structure):
    _fields_=[('tag',W.WORD),('channels',W.WORD),('rate',W.DWORD),('bytes_per_sec',W.DWORD),
              ('align',W.WORD),('bits',W.WORD),('extra',W.WORD)]


class Header(C.Structure):
    _fields_=[('data',C.c_void_p),('length',W.DWORD),('recorded',W.DWORD),('user',C.c_size_t),
              ('flags',W.DWORD),('loops',W.DWORD),('next',C.c_void_p),('reserved',C.c_size_t)]


class Output:
    def __init__(self,frames=480,count=12):
        self.api=C.WinDLL('winmm');self.handle=W.HANDLE();self.headers=[];self.buffers=[];self.used=[];self.cursor=0
        self.frames=frames;self.count=count;self.submitted=0;self.completed=0
        self.api.waveOutOpen.argtypes=[C.POINTER(W.HANDLE),W.UINT,C.POINTER(Format),C.c_size_t,C.c_size_t,W.DWORD]
        self.api.waveOutOpen.restype=W.UINT
        for name in ('waveOutPrepareHeader','waveOutUnprepareHeader','waveOutWrite'):
            function=getattr(self.api,name);function.argtypes=[W.HANDLE,C.POINTER(Header),W.UINT];function.restype=W.UINT
        for name in ('waveOutReset','waveOutClose'):
            function=getattr(self.api,name);function.argtypes=[W.HANDLE];function.restype=W.UINT
        fmt=Format(3,2,48000,48000*8,8,32,0)
        self.check(self.api.waveOutOpen(C.byref(self.handle),0xffffffff,C.byref(fmt),0,0,0))
        try:
            for _ in range(count):
                memory=C.create_string_buffer(frames*8);header=Header();header.data=C.addressof(memory);header.length=frames*8
                self.check(self.api.waveOutPrepareHeader(self.handle,C.byref(header),C.sizeof(header)))
                self.buffers.append(memory);self.headers.append(header);self.used.append(False)
        except Exception: self.close();raise

    @staticmethod
    def check(code):
        if code: raise RuntimeError(f'Windows 音频设备错误 {code}')

    def ready(self):
        header=self.headers[self.cursor]
        return not self.used[self.cursor] or bool(header.flags&1)

    def queued(self): return sum(used and not bool(header.flags&1) for used,header in zip(self.used,self.headers))

    def write(self,data):
        if len(data)!=self.frames*8: raise ValueError('设备块长度不匹配')
        if not self.ready(): raise RuntimeError('音频缓冲尚未完成')
        if self.used[self.cursor]: self.completed+=1
        C.memmove(self.buffers[self.cursor],data,len(data))
        self.check(self.api.waveOutWrite(self.handle,C.byref(self.headers[self.cursor]),C.sizeof(Header)))
        self.used[self.cursor]=True;self.cursor=(self.cursor+1)%self.count;self.submitted+=1

    def drain(self,timeout=1):
        deadline=time.monotonic()+timeout
        while self.queued() and time.monotonic()<deadline: time.sleep(.005)

    def close(self):
        if self.handle:
            self.api.waveOutReset(self.handle)
            for header in self.headers: self.api.waveOutUnprepareHeader(self.handle,C.byref(header),C.sizeof(Header))
            self.api.waveOutClose(self.handle);self.handle=W.HANDLE()

    def __enter__(self): return self
    def __exit__(self,*args): self.close()
