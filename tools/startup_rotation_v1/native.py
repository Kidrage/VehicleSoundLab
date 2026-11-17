import ctypes as C
from startup_character_v1.native import Starter
from startup_character_v1.expression import ExpressionStarter

from .contract import Mode,Profile,pack

class RotationStarter(Starter):
    def __init__(self,library,profile,seed):
        super().__init__(library,profile,seed)
        self.lib.sc_configure_rotation.argtypes=[C.c_void_p,C.POINTER(Profile),C.c_uint64];self.lib.sc_configure_rotation.restype=C.c_int
        p=pack(profile['rotation'])
        if not self.lib.sc_configure_rotation(self.handle,C.byref(p),seed):self.close();raise RuntimeError('Rotation model rejected')
        d=C.POINTER(C.c_double)
        self.lib.sc_process_expression.argtypes=[C.c_void_p,d,C.POINTER(C.c_int),d,d,d,d,C.POINTER(C.c_float),C.c_uint];self.lib.sc_process_expression.restype=C.c_int
    expression=ExpressionStarter.expression
