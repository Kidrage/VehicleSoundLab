"""Curvature of piecewise linear complex nodes on nonuniform end intervals."""
import numpy as np
from scipy import sparse


def curvature(positions,reference_step=256.):
    positions=np.asarray(positions,dtype=float);dt=np.diff(positions)
    if len(dt)<2 or np.any(dt<=0):raise ValueError('Invalid node positions')
    a=2*reference_step**2/(dt[:-1]*(dt[:-1]+dt[1:]))
    c=2*reference_step**2/(dt[1:]*(dt[:-1]+dt[1:]));b=-a-c
    row=np.repeat(np.arange(len(a)),3);col=np.column_stack((np.arange(len(a)),np.arange(len(a))+1,np.arange(len(a))+2)).ravel()
    return sparse.csr_matrix((np.column_stack((a,b,c)).ravel(),(row,col)),shape=(len(a),len(positions)))
