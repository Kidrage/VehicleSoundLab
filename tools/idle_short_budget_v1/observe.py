"""Shared diagnostic aperture for actual buses, separate from runtime DSP."""
import numpy as np
from idle_window_transfer_v1.observe import design,CENTRES


def observe(buses,frequencies,phasors,window_ms):
    buses=np.asarray(buses);assert buses.shape[0]==144000 and buses.ndim==2
    A=design(frequencies,phasors,len(buses));n=int(window_ms*48);w=.5-.5*np.cos(2*np.pi*np.arange(n)/n)
    values=[];conditions=[]
    for centre in CENTRES:
        first=int(centre-n//2);slab=A[first:first+n];gram=slab.T@(slab*w[:,None]);eig=np.linalg.eigvalsh(gram)
        if eig.min()<=np.finfo(float).eps*27*eig.max():raise ValueError('Unresolved bus basis')
        beta=np.linalg.solve(gram,slab.T@(buses[first:first+n]*w[:,None]))
        values.append((beta[:13]-1j*beta[13:26]).T);conditions.append(np.sqrt(eig.max()/eig.min()))
    return np.array(values),np.array(conditions)


def known(frequencies):
    from idle_window_transfer_v1.observe import known as single_known
    old,arrays=single_known(frequencies);main=arrays['audio'];z=arrays['phasors'];A=design(frequencies,z)
    detail=-.8*main+.002*A[:,0];buses=np.column_stack((main+detail,main,detail))
    expected=np.array([.2*arrays['expected'],arrays['expected'],-.8*arrays['expected']]);expected[[0,2],0]+=.002
    rows=[]
    for ms in [50,100,200]:
        c,condition=observe(buses,frequencies,z,ms);error=float(abs(c-expected).max());assert error<1e-10
        rows.append(dict(window_ms=ms,coefficient_error=error,additive_error=float(abs(c[:,0]-c[:,1]-c[:,2]).max())))
    return dict(single_FM=old,multibus=rows),dict(buses=buses,phasors=z,expected=expected)
