"""Chirp-aware local harmonic phases in an explicitly supplied coordinate.

Microphone coefficients are observations, not separated engine-bank pressure.
No RPM inference, phase unwrapping across arbitrary windows or source playback.
"""
from dataclasses import dataclass, asdict
import numpy as np
from scipy import linalg


@dataclass(frozen=True)
class PhaseFitSettings:
    window_seconds: float = .128
    maximum_harmonics: int = 128
    upper_hz: float = 8000
    maximum_gram_condition: float = 1e7
    closure_relative_amplitude_floor: float = .03


def integrated_cycles(times, frequency, query):
    t=np.asarray(times,dtype=float);f=np.asarray(frequency,dtype=float);q=np.asarray(query,dtype=float)
    if t.ndim!=1 or len(t)<3 or f.shape!=t.shape or not all(np.isfinite(v).all() for v in [t,f,q]):
        raise ValueError('Finite supplied frequency path and query required')
    if np.any(np.diff(t)<=0) or np.min(f)<=0 or np.min(q)<t[0]-1e-10 or np.max(q)>t[-1]+1e-10:
        raise ValueError('Positive ordered path and in-bounds queries required; no extrapolation')
    q=np.clip(q,t[0],t[-1]);index=np.clip(np.searchsorted(t,q,side='right')-1,0,len(t)-2)
    accumulated=np.r_[0,np.cumsum(.5*(f[:-1]+f[1:])*np.diff(t))]
    delta=q-t[index];slope=(f[index+1]-f[index])/(t[index+1]-t[index])
    return accumulated[index]+f[index]*delta+.5*slope*delta**2


def fit(audio,rate,origin,times,frequency,center,settings=PhaseFitSettings()):
    x=np.asarray(audio,dtype=float)
    if x.ndim!=2 or x.shape[1]!=2 or not np.isfinite(x).all() or rate<16000:
        raise ValueError('Finite unchanged two-channel audio required')
    if not 0<settings.window_seconds<=1 or not 1<=settings.maximum_harmonics<=128:
        raise ValueError('Bounded window and native DNA harmonic capacity required')
    first=round((center-settings.window_seconds/2-origin)*rate)
    stop=first+round(settings.window_seconds*rate)
    if first<0 or stop>len(x):raise ValueError('Window outside supplied audio')
    t=origin+np.arange(first,stop)/rate;center=float(center)
    cycles=integrated_cycles(times,frequency,t)-float(integrated_cycles(times,frequency,[center])[0])
    f=np.interp(t,times,frequency);root=float(np.interp(center,times,frequency))
    count=min(settings.maximum_harmonics,int(min(settings.upper_hz,.40*rate)/max(f)))
    if count<3 or len(t)<4*(2*count+1):raise ValueError('Insufficient supported harmonics/samples')
    phase=2*np.pi*cycles[:,None]*np.arange(1,count+1)[None,:]
    design=np.column_stack([np.ones(len(t)),np.cos(phase),np.sin(phase)])
    window=np.hanning(len(t));weighted=design*np.sqrt(window[:,None])
    gram=weighted.T@weighted;eigenvalues=linalg.eigvalsh(gram,check_finite=False)
    condition=float(eigenvalues[-1]/max(eigenvalues[0],np.finfo(float).tiny))
    if not np.isfinite(condition) or condition>settings.maximum_gram_condition:
        return dict(status='unmeasured',reason='Ill-conditioned harmonic coordinate',gram_condition=condition)
    coefficients=linalg.cho_solve(linalg.cho_factor(gram,check_finite=False),weighted.T@(x[first:stop]*np.sqrt(window[:,None])),check_finite=False)
    z=coefficients[1:count+1]-1j*coefficients[count+1:]
    residual=x[first:stop]-design@coefficients
    error=np.sum(window[:,None]*residual**2,axis=0)/np.maximum(np.sum(window[:,None]*x[first:stop]**2,axis=0),1e-30)
    record=dict(status='measured',settings=asdict(settings),source_center_seconds=center,
        source_sample_indices=[first,stop],source_window_seconds=[float(t[0]),float(t[-1]+1/rate)],
        supplied_root_hz=root,frequency_span_hz=[float(min(f)),float(max(f))],harmonics=count,
        gram_condition=condition,weighted_fit_error_db_lr=(10*np.log10(np.maximum(error,1e-30))).tolist(),
        fitted_dc_lr=coefficients[0].tolist(),real=z.real.tolist(),imag=z.imag.tolist(),
        phase_origin='Supplied integrated phase is zero at the window centre, common to both microphone channels.',
        limits='Local constant complex harmonic coefficients; source frequency path supplied over the whole window. Fit error is not physical noise energy or realism.')
    return record


def complex_coefficients(record):
    if record['status']!='measured':raise ValueError('Measured record required')
    return np.asarray(record['real'])+1j*np.asarray(record['imag'])


def curvature(z,relative_floor=.03):
    """Adjacent phase curvature, invariant to constant and linear order phase."""
    z=np.asarray(z);amplitude=abs(z)
    if z.ndim!=2 or z.shape[1]!=2 or len(z)<3:raise ValueError('Complex harmonic/channel array required')
    unit=z/np.maximum(amplitude,1e-30)
    value=unit[:-2]*unit[1:-1].conj()**2*unit[2:]
    minimum=np.minimum(np.minimum(amplitude[:-2],amplitude[1:-1]),amplitude[2:])
    usable=minimum>=relative_floor*amplitude.max(axis=0)
    return value,minimum**2,usable


def transfer_check(past,future,purge_seconds=.2):
    if future['source_window_seconds'][0]-past['source_window_seconds'][1]<purge_seconds:
        raise ValueError('Past/future fitting windows require explicit sample-support purge')
    a=complex_coefficients(past);b=complex_coefficients(future);count=min(len(a),len(b))
    ca,wa,ma=curvature(a[:count]);cb,wb,mb=curvature(b[:count]);mask=ma&mb
    rows=[]
    for channel in range(2):
        selected=mask[:,channel];weight=wb[selected,channel]
        if selected.sum()<3:
            rows.append(dict(status='unmeasured',reason='Fewer than three strong adjacent triplets in both windows',triplets=int(selected.sum())))
            continue
        error=float(np.sum(weight*abs(cb[selected,channel]-ca[selected,channel])**2)/weight.sum())
        flat=float(np.sum(weight*abs(cb[selected,channel]-1)**2)/weight.sum())
        rows.append(dict(status='measured',triplets=int(selected.sum()),
            center_harmonic_indices=(np.flatnonzero(selected)+2).tolist(),
            future_weighted_phase_chord_error=error,zero_curvature_chord_error=flat,
            learned_over_zero_error_db=float(10*np.log10(max(error,1e-30)/max(flat,1e-30))),
            weighted_phase_drift_degrees=float(np.sum(weight*abs(np.angle(cb[selected,channel]*ca[selected,channel].conj())))/weight.sum()*180/np.pi)))
    return dict(past_support_seconds=past['source_window_seconds'],future_support_seconds=future['source_window_seconds'],
        support_gap_seconds=future['source_window_seconds'][0]-past['source_window_seconds'][1],channels=rows,
        conditioning='Future amplitudes supply declared weights; future supplied frequency path is known. Only prior phase-curvature values are predicted. No waveform/amplitude/RPM forecasting or stochastic-source inference.')


def dna_text(root,z):
    z=np.asarray(z)
    if z.ndim!=1 or not 1<=len(z)<=128 or not 10<=root<=4000 or not np.isfinite(z).all():
        raise ValueError('Native scalar DNA root and finite harmonic coefficients required')
    return f'VSL_DNA 1 {root:.17g} {len(z)}\n'+''.join(f'{abs(v):.17g} {np.angle(v):.17g}\n' for v in z)
