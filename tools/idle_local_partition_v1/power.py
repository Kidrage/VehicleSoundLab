"""Exact conditional finite-window power for stationary FIR innovations and post gain."""
import numpy as np
from scipy import fft,signal
from .partition import BANDS,RATE


def expected(taps,envelope):
    h=np.asarray(taps);a=np.asarray(envelope);n=len(a)
    if len(h)>=n/2:raise ValueError('Expected FIR support shorter than half the observation')
    window=signal.windows.hann(n,sym=False);a=a*window
    size=fft.next_fast_len(2*n-1)
    ac=fft.irfft(abs(fft.rfft(a,size))**2,size)[:len(h)]
    length=fft.next_fast_len(2*len(h)-1)
    hc=fft.irfft(abs(fft.rfft(h,length))**2,length)[:len(h)]
    positive=ac*hc;correlation=np.zeros(n);correlation[:len(h)]=positive
    if len(h)>1:correlation[-len(h)+1:]=positive[1:][::-1]
    spectrum=np.fft.rfft(correlation).real/(n*sum(window**2))
    scale=float(np.max(abs(spectrum)))
    if spectrum.min() < -1e-12*scale:raise ValueError('Indefinite expected finite-window spectrum')
    # Do not clip tiny roundoff: its signed value remains in diagnostic spectra.
    if n%2:spectrum[1:]*=2
    else:spectrum[1:-1]*=2
    hz=np.fft.rfftfreq(n,1/RATE)
    bands=np.array([np.sum(spectrum[(hz>=lo)&(hz<hi)]) for lo,hi in BANDS])
    return bands,spectrum


def solve(matrix,target):
    matrix=np.asarray(matrix);target=np.asarray(target)
    if np.linalg.matrix_rank(matrix)!=2:raise ValueError('Unresolved low-band power matrix')
    gains_squared=np.linalg.solve(matrix,target)
    if np.any(gains_squared<=0):raise ValueError('Nonpositive low-band allocation; no clipping')
    return gains_squared


def known():
    h=np.array([.7,-.2,.1,.05]);n=81;t=np.arange(n)
    window=signal.windows.hann(n,sym=False);results=[]
    for label,envelope in [('constant',np.ones(n)),('varying',1+.2*np.cos(2*np.pi*t/n)+.1*np.sin(6*np.pi*t/n))]:
        bands,actual=expected(h,envelope)
        # Each independent input maps to finite output; every DFT-bin variance sums operator magnitudes.
        operator=np.zeros((n,n+len(h)-1))
        for i in range(n):
            for j in range(len(h)):operator[i,i+len(h)-1-j]=h[j]*window[i]*envelope[i]
        dft=np.exp(-2j*np.pi*np.arange(n//2+1)[:,None]*np.arange(n)/n)
        expected_bins=np.sum(abs(dft@operator)**2,axis=1)/(n*sum(window**2));expected_bins[1:]*=2
        error=float(abs(actual-expected_bins).max());assert error<1e-12
        parseval=float(abs(actual.sum()-np.dot(h,h)*sum((window*envelope)**2)/sum(window**2)))
        assert parseval<1e-12
        results.append(dict(label=label,all_bins_direct_operator_error=error,weighted_parseval_error=parseval))
    matrix=np.array([[.9,.02],[.03,.8]]);truth=np.array([.002,.0007])
    assert abs(solve(matrix,matrix@truth)-truth).max()<1e-14
    try:solve(matrix,np.array([-.1,.1]))
    except ValueError:negative_rejected=True
    else:raise AssertionError('Infeasible gain was accepted')
    return dict(spectral_controls=results,positive_gain_recovery=True,negative_allocation_rejected=negative_rejected)
