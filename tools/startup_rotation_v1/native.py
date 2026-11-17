import ctypes as C
from startup_character_v1.native import Starter
from startup_character_v1.expression import ExpressionStarter

class Mode(C.Structure):
    _fields_=[('hz',C.c_double),('width_hz',C.c_double),('amplitude',(C.c_double*2)*3),('phase',C.c_double*2),('band',C.c_uint)]
class Profile(C.Structure):
    _fields_=[('count',C.c_uint),('bands',C.c_uint),('flutter_hz',C.c_double),('coherence',C.c_double),('cosine',(C.c_double*2)*8),('sine',(C.c_double*2)*8),('mode',Mode*96)]

def pack(doc):
    p=Profile();p.count=len(doc['modes']);p.bands=len(doc['bands']);p.flutter_hz=doc['flutter_hz'];p.coherence=doc['coherence']
    if not 1<=p.count<=96 or not 1<=p.bands<=8:raise ValueError('Invalid model size')
    for out,row in zip(p.cosine,doc['cosine']):out[:]=row
    for out,row in zip(p.sine,doc['sine']):out[:]=row
    for out,row in zip(p.mode,doc['modes']):
        out.hz=row['hz'];out.width_hz=row['width_hz'];out.phase[:]=row['phase'];out.band=row['band']
        for a,b in zip(out.amplitude,row['amplitude']):a[:]=b
    return p

class RotationStarter(Starter):
    def __init__(self,library,profile,seed):
        super().__init__(library,profile,seed)
        self.lib.sc_configure_rotation.argtypes=[C.c_void_p,C.POINTER(Profile),C.c_uint64];self.lib.sc_configure_rotation.restype=C.c_int
        p=pack(profile['rotation'])
        if not self.lib.sc_configure_rotation(self.handle,C.byref(p),seed):self.close();raise RuntimeError('Rotation model rejected')
        d=C.POINTER(C.c_double)
        self.lib.sc_process_expression.argtypes=[C.c_void_p,d,C.POINTER(C.c_int),d,d,d,d,C.POINTER(C.c_float),C.c_uint];self.lib.sc_process_expression.restype=C.c_int
    expression=ExpressionStarter.expression
