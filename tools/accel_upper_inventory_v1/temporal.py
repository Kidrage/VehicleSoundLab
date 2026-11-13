"""Mixed upper-band temporal statistics; not an engine-source detector."""
import numpy as np
from scipy import signal
from idle_excitation_moments_v1.moments import describe


def observe(audio,plan):
    sos=np.array([signal.butter(4,band,btype='bandpass',fs=48000,output='sos') for band in plan['bands_hz']])
    bands=np.column_stack([signal.sosfilt(s,audio[:,0])[4800:-4800] for s in sos])
    count=len(bands)//480;power=np.mean(bands[:count*480].reshape(count,480,2)**2,axis=1)
    centered=power-power.mean(axis=0);cov=centered.T@centered/count
    normalized=cov/np.outer(power.mean(axis=0),power.mean(axis=0))
    correlation=cov/np.sqrt(np.outer(cov.diagonal(),cov.diagonal()))
    return dict(moments=describe(bands),energy_windows=count,
        energy_CV=(np.std(power,axis=0)/np.mean(power,axis=0)).tolist(),
        normalized_energy_covariance=normalized.tolist(),energy_correlation=correlation.tolist()),dict(
        audio=audio,filtered=bands,power=power,sos=sos)
