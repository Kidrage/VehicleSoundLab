"""Compensated FP64 products and sums without assuming a wider NumPy dtype.

Restricted operand range keeps Dekker splitting and all product error terms
normal. This is an offline numerical primitive, not an OSC or DSP runtime.
"""
import math
import numpy as np


def products(a,b):
    a,b=np.broadcast_arrays(np.asarray(a),np.asarray(b))
    if (a.dtype!=np.float64 or b.dtype!=np.float64 or not np.isfinite(a).all() or not np.isfinite(b).all()
        or any(np.any((np.abs(v)>2.**400)|((v!=0)&(np.abs(v)<2.**-400))) for v in (a,b))):
        raise ValueError('Finite FP64 operands within explicit normal-product range required')
    splitter=134217729.
    ca=splitter*a;ah=ca-(ca-a);al=a-ah
    cb=splitter*b;bh=cb-(cb-b);bl=b-bh
    high=a*b
    low=((ah*bh-high)+ah*bl+al*bh)+al*bl
    return high,low


def matvec(matrix,vector):
    matrix,vector=np.asarray(matrix),np.asarray(vector)
    if matrix.ndim!=2 or vector.shape!=(matrix.shape[1],) or matrix.shape[1]>2000000:
        raise ValueError('Bounded complete real matrix and vector required')
    result=np.empty(len(matrix));block=max(1,262144//max(1,matrix.shape[1]))
    for first in range(0,len(matrix),block):
        high,low=products(matrix[first:first+block],vector[None,:])
        for j,(p,e) in enumerate(zip(high,low)):
            result[first+j]=math.fsum(p.tolist()+e.tolist())
    if not np.isfinite(result).all():raise ValueError('Finite compensated output required')
    return result


def dot(a,b):return float(matvec(np.asarray(a)[None,:],np.asarray(b))[0])
