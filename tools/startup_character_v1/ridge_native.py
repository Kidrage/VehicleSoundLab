import ctypes as C
from .native import Starter

class Ridge(C.Structure):
    _fields_=[('start_frame',C.c_uint),('frames',C.c_uint),('hz',C.c_double),('slew',C.c_double),('amplitude',C.c_double*2),('phase',C.c_double*2)]

class RidgeStarter(Starter):
    def __init__(self,library,profile,seed):
        super().__init__(library,profile,seed)
        self.lib.sc_configure_ridges.argtypes=[C.c_void_p,C.POINTER(Ridge),C.c_uint,C.c_uint,C.c_double,C.c_double,C.c_uint64]
        rows=(Ridge*len(profile['ridges']))()
        for out,row in zip(rows,profile['ridges']):
            out.start_frame=row['start_frame'];out.frames=row['frames'];out.hz=row['hz'];out.slew=row['slew_hz_per_second']
            out.amplitude[:]=row['amplitude'];out.phase[:]=row['phase']
        if not self.lib.sc_configure_ridges(self.handle,rows,len(rows),profile['reference_frames'],profile['ridge_variation'],profile['ridge_pitch'],seed):
            self.close();raise RuntimeError('Sparse moving OSC recipe rejected')
