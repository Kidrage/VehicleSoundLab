"""Exact real aperture adjoint and white source-noise covariance trace."""
import numpy as np


def adjoint(operator,rows,frames):
    values=np.asarray(rows)
    vector=values.ndim==1
    if vector:
        values=values[:,None]
    count=len(operator.starts)*len(operator.orders)
    if values.shape[0]!=2*count:
        raise ValueError('Real aperture rows have incompatible shape')
    if min(operator.bins)<=0 or max(operator.bins)>=operator.size//2:
        raise ValueError('This real adjoint requires interior positive frequency bins')
    positive=(values[:count]+1j*values[count:]).reshape(len(operator.starts),len(operator.orders),-1)
    out=np.zeros((frames,values.shape[1]))
    factor=operator.size/operator.window.sum()
    for index,start in enumerate(operator.starts):
        spectrum=np.zeros((operator.size//2+1,values.shape[1]),dtype=complex)
        spectrum[operator.bins]=positive[index]*operator.rotations[index,:,None].conj()
        local=np.fft.irfft(spectrum,n=operator.size,axis=0)*factor*operator.window[:,None]
        out[start:start+operator.size]+=local
    return out[:,0] if vector else out


def covariance_trace(operator):
    return float(len(operator.starts)*len(operator.orders)*4*
        np.sum(operator.window**2)/operator.window.sum()**2)
