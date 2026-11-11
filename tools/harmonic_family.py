"""Offline harmonic-comb observations with explicit sub/octave alternatives.

This estimates a repeated spectral spacing, not engine RPM or cylinder count.
The recording channels are observations and are never relabelled as banks.
"""
import numpy as np
from scipy import signal, ndimage


def spectrum(audio, rate, seconds=.5, hop=.05):
    length=round(seconds*rate);step=round(hop*rate)
    hz,t,z=signal.stft(audio,rate,nperseg=length,noverlap=length-step,
        nfft=65536,axis=0,boundary=None,padded=False,scaling='psd')
    return hz,t,abs(z)**2


def comb_scores(hz,power,candidates,upper=1600,max_order=24):
    # Whiten the smooth recorded spectrum before testing harmonic spacings.
    db=10*np.log10(np.maximum(power,1e-30))
    bins=max(3,round(35/(hz[1]-hz[0]))|1)
    floor=ndimage.median_filter(db,size=bins,mode='nearest')
    contrast=30*np.tanh(np.maximum(db-floor,0)/30)
    scores=[]
    for fundamental in candidates:
        orders=np.arange(1,min(max_order,int(upper/fundamental))+1)
        weights=orders**-.25
        values=np.interp(orders*fundamental,hz,contrast)
        scores.append(float(values@weights/weights.sum()))
    return np.asarray(scores)


def track(audio,rate,seconds=.5,hop=.05,lower=30,upper=180):
    hz,t,p=spectrum(audio,rate,seconds,hop)
    candidates=np.arange(lower,upper+.025,.05)
    rows=[]
    for j,at in enumerate(t):
        mean=p[:,:,j].mean(axis=1)
        score=comb_scores(hz,mean,candidates)
        peaks=signal.find_peaks(score,distance=round(2/.05))[0]
        peaks=peaks[np.argsort(score[peaks])[::-1]][:6]
        best=int(peaks[0])
        rows.append(dict(seconds=float(at),spacing_hz=float(candidates[best]),score_db=float(score[best]),
            candidates=[dict(spacing_hz=float(candidates[k]),score_db=float(score[k])) for k in peaks]))
    return hz,t,p,rows
