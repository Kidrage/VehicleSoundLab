import ctypes as C
from pathlib import Path
import numpy as np

class Starter:
    def __init__(self,library,profile,seed):
        self.lib=C.CDLL(str(library))
        self.lib.sc_open.argtypes=[C.c_char_p]*3+[C.POINTER(C.c_double),C.c_double,C.c_uint64];self.lib.sc_open.restype=C.c_void_p
        self.lib.sc_close.argtypes=[C.c_void_p]
        self.lib.sc_process.argtypes=[C.c_void_p,C.POINTER(C.c_double),C.POINTER(C.c_int),C.c_double,C.POINTER(C.c_float),C.c_uint]
        env=(C.c_double*9)(*profile['envelope'])
        self.handle=self.lib.sc_open(*[str(Path(p['path'])).encode('utf-8') for p in profile['profiles']],env,profile['variation'],seed)
        if not self.handle:raise RuntimeError('Starter profile rejected')
    def close(self):
        if self.handle:self.lib.sc_close(self.handle);self.handle=None
    def process(self,progress,gate,strength=1.):
        progress=np.ascontiguousarray(progress,dtype=np.float64);gate=np.ascontiguousarray(gate,dtype=np.int32)
        assert progress.ndim==1 and gate.shape==progress.shape
        out=np.empty((len(progress),2),dtype=np.float32)
        if not self.lib.sc_process(self.handle,progress.ctypes.data_as(C.POINTER(C.c_double)),gate.ctypes.data_as(C.POINTER(C.c_int)),strength,out.ctypes.data_as(C.POINTER(C.c_float)),len(progress)):
            raise RuntimeError('Starter processing rejected')
        return out
