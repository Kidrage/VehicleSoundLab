"""Stereo spectral power matrices, with explicit conjugate(L)*R convention."""
import numpy as np
from scipy import signal

BANDS = [(1200,1500),(1500,1900),(1900,2400),(2400,3000),
         (3000,3800),(3800,4800),(4800,6000),(6000,8000)]


def matrices(audio, bands=BANDS):
    if audio.ndim != 2 or audio.shape[1] != 2 or len(audio)<4096 or not np.isfinite(audio).all():
        raise ValueError('Finite stereo with sufficient Welch windows required')
    kw = dict(fs=48000, nperseg=2048, noverlap=1536, window='hann', detrend=False, scaling='density')
    hz, power = signal.welch(audio, axis=0, **kw)
    _, cross = signal.csd(audio[:,0], audio[:,1], **kw)
    result = []
    for low, high in bands:
        select = (hz>=low)&(hz<high)
        diagonal = power[select].sum(axis=0)*(hz[1]-hz[0])
        xy = complex(cross[select].sum()*(hz[1]-hz[0]))
        result.append(dict(hz=[low,high], power=diagonal.tolist(), cross=[xy.real,xy.imag]))
    return result


def error(reference, candidate):
    result = []
    for a, b in zip(reference, candidate):
        assert a['hz']==b['hz']
        p, q = np.asarray(a['power']), np.asarray(b['power'])
        def coh(row):
            return complex(*row['cross'])/max(np.sqrt(np.prod(row['power'])),1e-30)
        c, d = coh(a), coh(b)
        result.append(dict(hz=a['hz'], power_delta_db=(10*np.log10((q+1e-30)/(p+1e-30))).tolist(),
            reference_coherence=[c.real,c.imag], candidate_coherence=[d.real,d.imag],
            complex_coherence_error=float(abs(c-d))))
    return result
