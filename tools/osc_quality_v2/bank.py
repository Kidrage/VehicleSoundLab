"""Dense complex-envelope oscillator diagnostic, not a procedural engine.

The complete bank is deliberately an information-preserving transform of the
same recording. Coefficients retain its whole trajectory; do not mistake this
for a low-dimensional RPM/load model or evidence of learned engine physics.
"""
import numpy as np


def fit(audio, window=512, limit=None):
    hop=window//4
    taper=.5-.5*np.cos(2*np.pi*np.arange(window)/window)
    result=[]
    for start in range(-window+hop,len(audio),hop):
        grain=np.zeros(window)
        lo,hi=max(start,0),min(start+window,len(audio))
        grain[lo-start:hi-start]=audio[lo:hi]
        z=np.fft.rfft(grain*taper)
        indices=np.arange(len(z))
        if limit is not None:
            indices=np.sort(np.argsort(abs(z))[-limit:])
        result.append((start,indices,z[indices]))
    return result


def render(grains, length, window=512):
    taper=(.5-.5*np.cos(2*np.pi*np.arange(window)/window))/1.5
    y=np.zeros(length)
    for start,indices,coefficients in grains:
        bins=np.zeros(window//2+1,dtype=complex)
        bins[indices]=coefficients
        grain=np.fft.irfft(bins,n=window)*taper
        lo,hi=max(start,0),min(start+window,length)
        y[lo:hi]+=grain[lo-start:hi-start]
    return y


def export(path, grains, rate, length, window=512):
    with path.open('w',encoding='ascii',newline='\n') as f:
        f.write(f'VSL_DENSE_OSC 1 {rate} {length} {window} {window//4} {len(grains)}\n')
        for start,indices,coefficients in grains:
            f.write(f'{start} {len(indices)}\n')
            for k,z in zip(indices,coefficients):
                f.write(f'{k} {z.real:.17g} {z.imag:.17g}\n')
