"""Apply the ORIGINAL decoder's exact endcaps once, outside generation."""
import numpy as np


def canonical_rows(cumulative):
    result=np.array(cumulative,dtype=float,copy=True)
    result[...,0]=0.;result[...,-1]=1.
    if not np.isfinite(result).all() or np.any(np.diff(result,axis=-1)<=0):
        raise ValueError('Strictly positive canonical cell probabilities required')
    return result
