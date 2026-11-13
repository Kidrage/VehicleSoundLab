"""Autonomous correlated slow amplitude, not a replayed source trajectory."""
import numpy as np
from idle_material_v1.features import spectrum
from sustain_osc_v1.oracle import Gaussian


def observations(audio,plan):
    n,hop=plan['envelope_window_frames'],plan['envelope_hop_frames']
    return np.asarray([spectrum(audio[j:j+n],plan['detail_bands_hz'])['power'][:,0]
        for j in range(0,len(audio)-n+1,hop)])


def fit(audio,plan):
    power=observations(audio,plan)
    values=.5*np.log(np.maximum(power,1e-30));values-=values.mean(axis=0)
    covariance=values.T@values/len(values)
    raw=float(np.sum(values[:-1]*values[1:])/max(np.sum(values[:-1]**2),1e-30))
    alpha=max(0.,min(plan['envelope_correlation_ceiling'],raw))
    covariance+=np.eye(len(covariance))*plan['envelope_covariance_ridge']
    np.linalg.cholesky(covariance)
    return dict(covariance=covariance.tolist(),alpha=alpha,raw_alpha=raw,
        hop_frames=plan['envelope_hop_frames'],strength=plan['envelope_strength'],
        evidence=dict(training_windows=len(values),training_log_amplitude_std=values.std(axis=0).tolist(),
            meaning='Full recorded band-energy proxy, not separated mechanical modulation'))


def states(model,frames,seed):
    cov=np.asarray(model['covariance']);cholesky=np.linalg.cholesky(cov)
    count=(frames-1)//model['hop_frames']+2
    rng=Gaussian(seed^0xD1B54A32D192ED03)
    normal=np.fromiter((rng.next() for _ in range(count*len(cov))),dtype=float).reshape(count,len(cov))
    state=np.empty_like(normal);state[0]=cholesky@normal[0]
    a=model['alpha']
    for i in range(1,count):state[i]=a*state[i-1]+np.sqrt(1-a*a)*(cholesky@normal[i])
    return state,normal


def gains(model,state,frames):
    hop=model['hop_frames'];index=np.arange(frames)//hop
    u=.5-.5*np.cos(np.pi*(np.arange(frames)%hop)/hop)
    value=(1-u[:,None])*state[index]+u[:,None]*state[index+1]
    variance=np.diag(model['covariance'])[None,:]*((1-u)**2+u*u+2*model['alpha']*u*(1-u))[:,None]
    s=model['strength']
    return np.exp(s*value-s*s*variance)


def controls(plan):
    # Full-window, bin-centred tones give exact independent band powers.
    rate=plan['sample_rate'];t=np.arange(3*rate)/rate
    frequencies=[200,800,1600,3000,6000,10000];amps=np.array([.1,.08,.06,.04,.03,.02])
    x=sum(a*np.cos(2*np.pi*f*t) for a,f in zip(amps,frequencies))
    measured=observations(np.column_stack((x,x)),plan)
    error=float(abs(measured-.5*amps**2).max());assert error<1e-12
    model=dict(covariance=[[.04,.01],[.01,.09]],alpha=.7,hop_frames=960,strength=.5)
    state,normal=states(model,3500,149921)
    l=np.linalg.cholesky(model['covariance']);oracle=l@normal[0]
    assert abs(oracle-state[0]).max()<1e-14
    for i in range(1,len(state)):
        oracle=.7*oracle+np.sqrt(1-.7**2)*(l@normal[i])
        assert abs(oracle-state[i]).max()<1e-14
    # Interpolation variance exactly matches w^T covariance w.
    u=.31;a=.7;mat=np.array([[1,a],[a,1]])
    variance=float(np.array([1-u,u])@mat@np.array([1-u,u]))
    assert abs(variance-((1-u)**2+u*u+2*a*u*(1-u)))<1e-15
    g=gains(dict(model,strength=0),state,3500);assert np.array_equal(g,np.ones_like(g))
    return dict(analytic_band_power_error=error,state_recurrence=True,interpolation_variance=True,zero_strength_exact=True)
