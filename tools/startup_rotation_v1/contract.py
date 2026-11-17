"""Standard-library-only native model layout, shared by authors and the App."""
import ctypes as C

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
