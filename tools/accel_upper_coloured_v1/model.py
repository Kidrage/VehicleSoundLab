"""Compose the qualified finite energy observer with a multistream Gaussian FIR carrier."""
import numpy as np
from scipy import signal
from accel_upper_am_v1.model import compile_observer
from accel_upper_carrier_v1.spectral import covariance


def compile_matrix_observer(impulse,tile,size=480,lags=None):
    h=np.asarray(impulse)
    if h.ndim!=3 or h.shape[1]!=4:raise ValueError('Expected taps x four outputs x independent inputs')
    op=compile_observer(np.ones((1,4)),tile,size,lags)
    padded=1<<int((2*len(h)-2).bit_length());support,R=covariance(h,padded)
    power=np.diag(R[len(h)-1]).copy()
    if not np.all(power>0):raise ValueError('All four Gaussian carrier coordinates require positive variance')
    native=op['native_lags'];indices=native-int(support[0]);valid=(indices>=0)&(indices<len(support))
    squared=np.zeros((len(native),4,4));squared[valid]=R[indices[valid]]**2/np.outer(power,power)
    op.update(carrier_squared_normalized=squared,power=power)
    return op


def generate_carrier(impulse,frames,seed):
    """Independent full FIR history gives a stationary carrier; no repeated source samples."""
    h=np.asarray(impulse);white=np.random.default_rng(seed).standard_normal((frames+len(h)-1,h.shape[2]))
    out=np.zeros((frames,h.shape[1]))
    for i in range(h.shape[1]):
        for q in range(h.shape[2]):out[:,i]+=signal.oaconvolve(white[:,q],h[:,i,q],mode='full')[len(h)-1:len(h)-1+frames]
    return white,out
