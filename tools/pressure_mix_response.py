"""Offline reconstruction of native events and a noncausal bandlimited diagnostic.

No car recordings are read here. The FFT method approximates the continuous
modal impulse's ideal Nyquist projection, then retains native base-rate delay
and gain. It is not a candidate causal realtime algorithm.
"""
from runtime_review import ROOT
import numpy as np
from scipy.signal import lfilter
from scipy.fft import rfft,irfft

NODES=np.arange(-3,5)


def amplitudes(events,meta,mode_index):
    mode=meta['modes'][mode_index]
    return events['gain']*mode['weight']*(1+events['shape']*(mode_index-1)*meta['shape_spread'])


def native_post(raw,gain,meta):
    delay=meta['sample_rate']*meta['right_delay_seconds'];integer=int(delay);fraction=delay-integer
    y=raw.copy();y[:,1]=0
    if integer==0:y[:,1]=(1-fraction)*raw[:,1]
    else:y[integer:,1]=(1-fraction)*raw[:-integer,1]
    y[integer+1:,1]+=fraction*raw[:-integer-1,1]
    return y*gain[:,None]


def recurrence(events,meta,gain):
    n=meta['frames'];sr=meta['sample_rate'];raw=np.zeros((n,2))
    for bank in range(2):
        ev=events[events['bank']==bank];indices=ev['frame'].astype(int)
        for i,mode in enumerate(meta['modes']):
            p=-1/mode['decay_seconds']+2j*np.pi*mode['hz'];impulses=np.zeros(n,complex)
            np.add.at(impulses,indices,amplitudes(ev,meta,i)*np.exp(p*ev['elapsed']))
            raw[:,bank]+=lfilter([1],[1,-np.exp(p/sr)],impulses).imag
    return native_post(raw,gain,meta)


def lagrange_weights(fraction):
    weights=np.ones((len(fraction),len(NODES)))
    for j,node in enumerate(NODES):
        for other in NODES:
            if other!=node:weights[:,j]*=(fraction-other)/(node-other)
    return weights


def transfer(frequency,mode):
    omega=2*np.pi*mode['hz'];alpha=1/mode['decay_seconds']
    return omega/((alpha+2j*np.pi*frequency)**2+omega**2)


def bandlimited(events,meta,gain,period_frames,oversample):
    """Finite periodic Fourier approximation with zero padding on both sides.

    Event delta trains use eight-point Lagrange deposition on a finer grid.
    Only base-rate Nyquist bins are retained and multiplied by the continuous
    transfer. irfft endpoints give trapezoid half weights at +/-Nyquist.
    """
    n=meta['frames'];sr=meta['sample_rate'];padding=(period_frames-n)//2
    assert period_frames%2==0 and padding>=sr//2
    f=np.fft.rfftfreq(period_frames,1/sr);spectra=np.zeros((len(f),2),complex)
    worst_bound=0.
    for bank in range(2):
        ev=events[events['bank']==bank]
        position=(ev['frame']-ev['elapsed']*sr+padding)*oversample
        integer=np.floor(position).astype(np.int64);fraction=position-integer
        weights=lagrange_weights(fraction);indices=integer[:,None]+NODES
        assert indices.min()>=0 and indices.max()<period_frames*oversample
        # Interpolation remainder bound for e^(-i theta*x), real and imaginary
        # separately, evaluated at the largest retained frequency pi/os.
        bounds=np.sqrt(2)*(np.pi/oversample)**8/40320*abs(np.prod(fraction[:,None]-NODES,axis=1))
        worst_bound=max(worst_bound,float(bounds.max()))
        for i,mode in enumerate(meta['modes']):
            grid=np.zeros(period_frames*oversample)
            np.add.at(grid,indices.ravel(),(amplitudes(ev,meta,i)[:,None]*weights).ravel())
            spectrum=rfft(grid)[:len(f)]
            spectra[:,bank]+=spectrum*transfer(f,mode)
    raw=irfft(spectra,n=period_frames,axis=0)[padding:padding+n]*sr
    return native_post(raw,gain,meta),dict(period_frames=period_frames,padding_frames_each_side=padding,
        oversample=oversample,lagrange_order=8,maximum_single_event_complex_phase_factor_error_bound=worst_bound,
        nyquist_endpoint='Trapezoid half weights for the finite Fourier integral; not a periodically sustained exact-Nyquist line.')


def ratios(a,b,sr):
    """Unweighted AC / 3-8k differences relative to original b, per channel."""
    n=len(a);f=np.fft.rfftfreq(n,1/sr);weight=np.full(len(f),2.);weight[0]=1
    if n%2==0:weight[-1]=1
    d=rfft(a-b,axis=0)/n;reference=rfft(b,axis=0)/n;bands={}
    for name,lo,hi in [('AC',0,sr/2),('3000_8000',3000,8000)]:
        select=(f>lo)&(f<=hi)
        numerator=np.sum(abs(d[select])**2*weight[select,None],axis=0)
        denominator=np.sum(abs(reference[select])**2*weight[select,None],axis=0)
        bands[name]=dict(difference_power=numerator.tolist(),reference_power=denominator.tolist(),
            difference_over_original_db=[float(10*np.log10(x/y)) if x>0 and y>0 else None for x,y in zip(numerator,denominator)])
    return dict(bands=bands,delta_peak=np.max(abs(a-b),axis=0).tolist(),
        original_rms=np.sqrt(np.mean(b*b,axis=0)).tolist(),replacement_rms=np.sqrt(np.mean(a*a,axis=0)).tolist())
