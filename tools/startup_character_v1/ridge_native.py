import ctypes as C
from .native import Starter

from .contract import Ridge,pack

class RidgeStarter(Starter):
    def __init__(self,library,profile,seed):
        super().__init__(library,profile,seed)
        self.lib.sc_configure_ridges.argtypes=[C.c_void_p,C.POINTER(Ridge),C.c_uint,C.c_uint,C.c_double,C.c_double,C.c_uint64]
        rows=pack(profile['ridges'])
        if not self.lib.sc_configure_ridges(self.handle,rows,len(rows),profile['reference_frames'],profile['ridge_variation'],profile['ridge_pitch'],seed):
            self.close();raise RuntimeError('Sparse moving OSC recipe rejected')
