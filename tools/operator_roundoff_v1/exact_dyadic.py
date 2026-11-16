"""Independent exact integer dot product of finite IEEE binary64 inputs.

Audit-only. Multiplication and reduction use Python integers, followed by one
Fraction-to-float rounding; no floating product, FFT, or compensated primitive.
"""
from fractions import Fraction
import numpy as np


def parts(values):
    values=np.asarray(values)
    if values.dtype!=np.float64 or not np.isfinite(values).all():raise ValueError('Finite binary64 inputs required')
    bits=values.view(np.uint64);exponent=((bits>>52)&2047).astype(np.int64)
    mantissa=(bits&((1<<52)-1))|((exponent!=0).astype(np.uint64)<<52)
    power=np.where(exponent==0,-1074,exponent-1075)
    sign=np.where(bits>>63,-1,1)
    return mantissa,power,sign


def dot_parts(left,right):
    a,ea,sa=left;b,eb,sb=right
    if a.shape!=b.shape or a.ndim!=1:raise ValueError('Equal finite vectors required')
    active=(a!=0)&(b!=0)
    if not active.any():return 0.
    exponents=(ea+eb)[active];origin=int(exponents.min());total=0
    for ma,mb,pa,sgn in zip(a[active],b[active],exponents,(sa*sb)[active]):
        total+=(int(ma)*int(mb)*int(sgn))<<int(pa-origin)
    return float(Fraction(total,1<<(-origin))) if origin<0 else float(total<<origin)


def dot(a,b):return dot_parts(parts(a),parts(b))


def matvec(matrix,vector):
    matrix,vector=np.asarray(matrix),np.asarray(vector)
    if matrix.ndim!=2 or vector.shape!=(matrix.shape[1],):raise ValueError('Complete matrix/vector required')
    right=parts(vector)
    return np.array([dot_parts(parts(row),right) for row in matrix])
