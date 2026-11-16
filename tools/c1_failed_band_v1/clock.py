"""Exact derivative extrema of each supported saved cubic clock interval."""
import numpy as np


def bounds(x,coefficients,first,last):
    x,c=np.asarray(x),np.asarray(coefficients)
    if (x.ndim!=1 or len(x)<2 or c.shape!=(4,len(x)-1) or np.iscomplexobj(x)
        or np.iscomplexobj(c) or not np.isfinite(x).all() or not np.isfinite(c).all()
        or np.any(np.diff(x)<=0) or not np.isfinite([first,last]).all()
        or first>=last or first<x[0] or last>x[-1]):
        raise ValueError('Finite supported cubic interval required')
    values=[]
    for k in range(len(x)-1):
        a,b=max(first,x[k])-x[k],min(last,x[k+1])-x[k]
        if a>b:continue
        candidates=[a,b]
        if c[0,k]!=0:
            at=-c[1,k]/(3*c[0,k])
            if a<at<b:candidates.append(at)
        values.extend((3*c[0,k]*t+2*c[1,k])*t+c[2,k] for t in candidates)
    low,high=float(min(values)),float(max(values))
    if low<=0:raise ValueError('Strict positive clock derivative required')
    return low,high
