"""Compact damped modes + shaped procedural excitation, without a sample table."""
import numpy as np
from scipy import signal
from .model import coefficients,synth,validate
from .measure import spectrum
from .band_scope import normalize,mask


def fit(observation,arrays,duration,gated=False):
    f,p,bg,excess,peaks,t,power=arrays;df=f[1]-f[0];claimed=np.zeros_like(excess,dtype=bool)
    scope=normalize(observation.get('analysis_scope'));scoped=scope['mode']=='band';eligible=mask(f,scope)
    modes=[]
    for k,measured in zip(peaks,observation['modal_observations']):
        support=np.arange(max(0,k-1),min(len(f),k+2));support=support[~claimed[support]]
        if scoped:support=support[eligible[support]]
        available=float(excess[support].sum()*df);claimed[support]=True
        b=next((b for b in observation['bands'] if b['hz'][0]<=f[k]<b['hz'][1]),observation['bands'][0])
        # Preserve a broadband remainder; 35% allocation is authoring policy, not measured source share.
        modes.append(dict(hz=measured['hz'],end_hz=measured['hz'],amplitude=float(np.sqrt(.35*2*available)),
            phase=measured['phase'],decay_seconds=b['decay_seconds']))
    bands=[]
    for b in observation['bands']:
        lo,hi=b['hz']
        center=float(np.sqrt(lo*hi));q=float(np.clip(center/(hi-lo),.15,30))
        num,den=coefficients(center,q)
        impulse=np.zeros(96000);impulse[0]=1
        variance=float(np.square(signal.lfilter(num,den,impulse)).sum()/3)
        band_modes=sum(m['amplitude']**2/2 for m in modes if lo<=m['hz']<hi)
        target=max(0,b['excess_power']-band_modes)
        amplitude=float(np.sqrt(target/max(variance,1e-12)))
        bands.append(dict(hz=center,q=q,amplitude=min(8,amplitude),attack_seconds=b['attack_seconds'],decay_seconds=b['decay_seconds']))
    profile=dict(gated=int(gated),duration_seconds=10. if gated else duration,
        attack_seconds=.012 if gated else min(b['attack_seconds'] for b in observation['bands']),
        release_seconds=.025 if gated else min(.025,duration/4),sweep_seconds=0.,level=1.,modes=modes,bands=bands)
    validate(profile)
    y=synth(profile,seconds=duration)
    target=observation['excess_mean_square'];actual=float(np.mean(y*y))
    full_actual=actual
    if scoped:
        target=observation['scoped_excess_mean_square'];frequency,generated=spectrum(y[:,None])
        actual=float(generated[mask(frequency,scope)].sum()*(frequency[1]-frequency[0]))
    profile['level']=float(np.clip(np.sqrt(target/max(actual,1e-30)),0,8))
    policy=dict(level_fit_target_excess_power=target,unscaled_generated_power=actual,
        policy='12 strongest excess PSD peaks; 35% of each 3-bin peak allocated to modes, remaining band power to four SOS noise bands; one global RMS fit.',
        limitations='Modal phase is one selected-channel window projection, not physical dry-source phase or full time-varying reconstruction. Event-wide ±0.2% offset is engineering; no fitted room IR.')
    if scoped:
        from .scoped_fit import calibrate
        # Retain the global fit only as a diagnostic; calibrate from level1 so
        # wide SOS tails cannot silently steal energy from a quiet high band.
        profile['level']=1.
        profile,calibration=calibrate(profile,observation,duration)
        policy.update(calibration,analysis_scope=scope,unscaled_generated_full_power=full_actual,
            policy='Declared-scope excess peaks and clipped-band SOS; bounded per-band actual-response gain calibration replaces global-only scaling.',
            limitations=policy['limitations']+' Scoped fitting is statistical subtraction; SOS leakage outside the requested band remains possible.')
    return validate(profile),policy
