"""Optional source-expression controls for the isolated procedural C voice."""
import ctypes as C
import numpy as np
from .ridge_native import RidgeStarter


class ExpressionStarter(RidgeStarter):
    def __init__(self,library,profile,seed):
        super().__init__(library,profile,seed)
        d=C.POINTER(C.c_double)
        self.lib.sc_process_expression.argtypes=[C.c_void_p,d,C.POINTER(C.c_int),d,d,d,d,C.POINTER(C.c_float),C.c_uint]
        self.lib.sc_process_expression.restype=C.c_int

    def expression(self,progress,gate,strength=1.,pitch=1.,core=1.,texture=1.):
        p=np.ascontiguousarray(progress,dtype=np.float64)
        g=np.ascontiguousarray(gate,dtype=np.int32)
        if p.ndim!=1 or g.shape!=p.shape:raise ValueError('One control per sample required')
        arrays=[np.ascontiguousarray(np.broadcast_to(x,p.shape),dtype=np.float64) for x in (strength,pitch,core,texture)]
        out=np.empty((len(p),2),dtype=np.float32)
        ptr=lambda x:x.ctypes.data_as(C.POINTER(C.c_double))
        if not self.lib.sc_process_expression(self.handle,ptr(p),g.ctypes.data_as(C.POINTER(C.c_int)),*[ptr(x) for x in arrays],out.ctypes.data_as(C.POINTER(C.c_float)),len(p)):
            raise RuntimeError('C expression controls rejected')
        return out


def smooth_curve(position,knots,values):
    """Coarse action controls, with zero slope at each named key point."""
    p=np.asarray(position);k=np.asarray(knots);v=np.asarray(values)
    if len(k)!=len(v) or len(k)<2 or not np.all(np.diff(k)>0):raise ValueError('Strictly ordered controls required')
    i=np.clip(np.searchsorted(k,p,side='right')-1,0,len(k)-2)
    u=np.clip((p-k[i])/(k[i+1]-k[i]),0,1);u=u*u*(3-2*u)
    return (1-u)*v[i]+u*v[i+1]
