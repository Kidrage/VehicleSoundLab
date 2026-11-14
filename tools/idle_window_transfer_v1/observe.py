"""Configurable diagnostic aperture on fixed centres; existing observer untouched."""
import numpy as np

CENTRES=16800+np.arange(116)*960
SELECTED=[1,2,4]


def design(frequencies,phasors,frames=144000):
    z=np.exp(2j*np.pi*np.arange(frames)[:,None]/48000*np.array(frequencies))
    z[:,SELECTED]=phasors
    return np.column_stack((z.real,z.imag,np.ones(frames)))


def observe(audio,frequencies,phasors,window_ms):
    A=design(frequencies,phasors,len(audio));n=int(window_ms*48);w=.5-.5*np.cos(2*np.pi*np.arange(n)/n)
    coefficients=[];condition=[]
    for centre in CENTRES:
        first=int(centre-n//2);slab=A[first:first+n];gram=slab.T@(slab*w[:,None]);e=np.linalg.eigvalsh(gram)
        if e.min()<=np.finfo(float).eps*len(gram)*e.max():raise ValueError('Unresolved joint aperture')
        b=np.linalg.solve(gram,slab.T@(audio[first:first+n]*w))
        coefficients.append(b[:13]-1j*b[13:26]);condition.append(float(np.sqrt(e.max()/e.min())))
    return np.array(coefficients),np.array(condition)


def known(frequencies):
    t=np.arange(144000)/48000;f=np.array(frequencies);amplitude=np.linspace(.01,.12,len(f))
    theta=2*np.pi*t[:,None]*f;theta[:,SELECTED]+=.23*np.sin(2*np.pi*t[:,None]*[1.1,2.3,3.7]+[.2,.7,1.1])
    theta+=np.arange(len(f))*.173;z=np.exp(1j*theta);audio=z.real@amplitude
    # Fixed nonselected initial phases remain complex regression coefficients.
    expected=amplitude*np.exp(1j*np.arange(len(f))*.173);expected[SELECTED]=amplitude[SELECTED]
    rows=[];arrays={}
    for ms in [50,100,200]:
        c,condition=observe(audio,f,z[:,SELECTED],ms);error=float(abs(c-expected).max())
        logstd=float(np.std(np.log(abs(c[:,SELECTED])),axis=0).max())
        assert error<1e-10 and logstd<1e-8
        rows.append(dict(window_ms=ms,coefficient_error=error,false_logstd=logstd,max_condition=float(condition.max())))
        arrays[str(ms)]=c
    return rows,dict(audio=audio,phasors=z[:,SELECTED],expected=expected,**arrays)
