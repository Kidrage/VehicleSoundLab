"""Power-modulation association with raw acoustic components, not a source detector."""
import numpy as np
from scipy import signal

N=4800
HOP=2400
BANDS=np.array([[30,120],[120,200],[200,400],[400,600]])


def features(audio,sos):
    real=np.column_stack([signal.sosfilt(s,audio[:,ch]) for s in sos for ch in range(2)])
    analytic=signal.hilbert(real,axis=0)
    return np.asarray(audio)[4800:-4800],abs(analytic[4800:-4800])**2


def observe(reference,power):
    if len(reference)!=len(power) or reference.shape[1]!=2 or power.shape[1]!=4:raise ValueError('Two references and four powers required')
    starts=np.arange(0,len(power)-N+1,HOP);w=signal.windows.hann(N,sym=False)
    X=np.array([np.fft.rfft((reference[s:s+N]-reference[s:s+N].mean(axis=0))*w[:,None],axis=0) for s in starts])
    Y=np.array([np.fft.rfft((power[s:s+N]-power[s:s+N].mean(axis=0))*w[:,None],axis=0) for s in starts])
    scale=np.full(N//2+1,2/(48000*np.dot(w,w)));scale[[0,-1]]/=2
    xx=np.mean(abs(X)**2,axis=0)*scale[:,None];yy=np.mean(abs(Y)**2,axis=0)*scale[:,None]
    xy=np.einsum('wfi,wfj->fij',X.conj(),Y)/len(starts)*scale[:,None,None]
    denominator=xx[:,:,None]*yy[:,None,:];valid=denominator>0;msc=np.zeros_like(denominator)
    np.divide(abs(xy)**2,denominator,out=msc,where=valid)
    if msc.max()>1+1e-12:raise ValueError('Coherence exceeds Cauchy-Schwarz limit')
    return dict(hz=np.fft.rfftfreq(N,1/48000),Pxx=xx,Pyy=yy,Cxy=xy,MSC=msc,valid=valid,starts=starts)


def summarize(values):
    hz=values['hz'];xx=values['Pxx'];yy=values['Pyy'];msc=values['MSC'];rows=[]
    for lo,hi in BANDS:
        select=(hz>=lo)&(hz<hi);modulation=yy[select].sum(axis=0)*10;low=xx[select].sum(axis=0)*10
        numerator=np.sum(msc[select]*yy[select,None,:],axis=0)*10
        fraction=np.zeros_like(numerator);np.divide(numerator,modulation[None,:],out=fraction,where=modulation[None,:]>0)
        rows.append(dict(band_hz=[int(lo),int(hi)],reference_power=low.tolist(),upper_power_modulation=modulation.tolist(),
            power_weighted_MSC=fraction.tolist(),modulation_present=(modulation>0).tolist()))
    return rows


def known():
    from numpy.polynomial.hermite import hermgauss
    t=np.arange(144000)/48000;z=np.exp(2j*np.pi*300*t);reference=np.column_stack((z.real,z.imag))
    envelope=(1+.4*z.real)**2;power=np.column_stack((envelope,envelope*.3,envelope*.1,envelope*.7))
    out=observe(reference,power);index=30;error=float(abs(out['MSC'][index]-1).max());assert error<1e-12
    scaled=observe(reference*.173,power*.013);gain_error=float(abs(scaled['MSC'][index]-out['MSC'][index]).max());assert gain_error<1e-12
    permutation=[2,0,3,1];swapped=observe(reference[:,::-1],power[:,permutation]);assert abs(swapped['MSC'][index]-out['MSC'][index][::-1][:,permutation]).max()<1e-12
    constant=observe(reference,np.ones_like(power));assert not np.any(constant['valid']) and not np.any(constant['MSC'])
    # A deterministic two-tone sum has power at the frequency difference.
    beating=abs(np.exp(2j*np.pi*5000*t)+.2*np.exp(2j*np.pi*5300*t))**2
    beat=observe(reference,np.tile(beating[:,None],(1,4)));beat_error=float(abs(beat['MSC'][index]-1).max());assert beat_error<1e-12
    q,w=hermgauss(9);x,y=np.meshgrid(q*np.sqrt(2),q*np.sqrt(2),indexing='ij');W=np.outer(w,w)/np.pi
    h=.6*x+.8*y;third=float(np.sum(W*x*(h*h-1)));assert abs(third)<1e-12
    return dict(AM_supported_bin_MSC_error=error,gain_invariance_error=gain_error,channel_permutation=True,
        constant_power_undefined=True,beating_supported_bin_MSC_error=beat_error,Gaussian_third_moment=third,
        source_or_excitation_detector=False),dict(reference=reference,power=power,beating_power=beating)
