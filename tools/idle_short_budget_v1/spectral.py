"""Finite native residual-band observations; no physical source-separation claim."""
import numpy as np
from scipy import signal
from idle_window_transfer_v1.observe import design

OFFSETS=np.array([[0,3],[3,8],[8,15]])


def project(buses,frequencies,phasors):
    A=design(frequencies,phasors,len(buses));lo,hi=12000,len(buses)-12000
    w=signal.windows.hann(hi-lo,sym=False);slab=A[lo:hi]
    beta=np.linalg.solve(slab.T@(slab*w[:,None]),slab.T@(buses[lo:hi]*w[:,None]))
    return buses-A@beta,beta


def spectra(values):
    values=np.asarray(values);n=len(values);w=signal.windows.hann(n,sym=False)
    z=np.fft.fft(values*w[:,None],axis=0);f=np.fft.fftfreq(n,1/48000)
    return f,z/(np.sqrt(n*np.dot(w,w)))


def summarize(buses,residual,phasors):
    lo,hi=12000,len(buses)-12000;f,raw=spectra(buses[lo:hi]);_,r=spectra(residual[lo:hi])
    _,baseband=spectra(residual[lo:hi]*phasors[lo:hi,0,None].conj())
    # Real inputs use the full signed FFT; no implicit one-sided doubling.
    mask=(abs(f)>=30)&(abs(f)<120)
    bands=np.array([np.sum(abs(baseband[(abs(f)>=a)&(abs(f)<b)])**2,axis=0) for a,b in OFFSETS])
    result=dict(raw30_120=np.sum(abs(raw[mask])**2,axis=0),residual30_120=np.sum(abs(r[mask])**2,axis=0),
        baseband_power=bands)
    if buses.shape[1]==3:
        result['raw30_120_cross']=np.array(np.sum(2*(raw[mask,1]*raw[mask,2].conj()).real))
        result['residual30_120_cross']=np.array(np.sum(2*(r[mask,1]*r[mask,2].conj()).real))
        result['baseband_cross']=np.array([np.sum(2*(baseband[(abs(f)>=a)&(abs(f)<b),1]*baseband[(abs(f)>=a)&(abs(f)<b),2].conj()).real) for a,b in OFFSETS])
        for key,cross in [('raw30_120','raw30_120_cross'),('residual30_120','residual30_120_cross'),('baseband_power','baseband_cross')]:
            error=float(abs(result[key][...,0]-result[key][...,1]-result[key][...,2]-result[cross]).max())
            assert error<1e-12
    return result


def known(frequencies):
    t=np.arange(144000)/48000;freq=np.array(frequencies);z=np.exp(2j*np.pi*t[:,None]*freq[[1,2,4]])
    A=design(freq,z);beta=np.random.default_rng(721791).normal(0,.01,(27,2));buses=A@beta
    residual,recovered=project(buses,freq,z);error=float(abs(residual).max());assert error<1e-12
    # Integer-bin control over the SAME2.5s ROI, 76Hz carrier/7.2Hz modulation.
    carrier=np.exp(2j*np.pi*76*t);a=.2;r=a*np.cos(2*np.pi*76*t)*np.cos(2*np.pi*7.2*t)
    f,Z=spectra((r*carrier.conj())[12000:-12000,None])
    positive=np.sum(abs(Z[(f>=6)&(f<8),0])**2);negative=np.sum(abs(Z[(f<=-6)&(f>-8),0])**2)
    # One low-frequency sideband amplitude a/4 gives power a^2/16 each.
    expected=a*a/16;side_error=max(abs(positive-expected),abs(negative-expected));assert side_error<1e-12
    mixed=buses+.01*np.cos(2*np.pi*(freq[1]+7.2)*t)[:,None]
    leftover,_=project(mixed,freq,z);rms=float(np.sqrt(np.mean(leftover[12000:-12000]**2)));assert rms>.003
    return dict(exact_projection_error=error,known_each_signed_sideband_power=expected,sideband_power_error=side_error,
        omitted_neighbor_surviving_rms=rms,source_residual_not_physical_noise=True),dict(audio=buses,phasors=z,beta=beta,
        residual=residual,sideband_residual=r,sideband_phasor=carrier)
