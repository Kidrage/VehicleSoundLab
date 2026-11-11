"""Offline diagnostic: 64 tracked OSC/channel plus shaped stochastic residual.
Same-excerpt fitting only. Never includes residual waveform playback in output.
"""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from scipy.optimize import nnls
from sinusoidal_experiment import synthesize
out=ROOT/'references/analysis/v02/hybrid';out.mkdir(parents=True,exist_ok=True)
x,sr=sf.read(ROOT/'references/clean/B_cabin_pull.wav',always_2d=True)
y=np.column_stack([synthesize(x[:,c],sr,64) for c in range(2)])
residual=x-y;stochastic=np.zeros_like(x);rng=np.random.default_rng(48271);measurements=[];basis=[]
valid=slice(sr//4,-sr//4)
for lo,hi in [(60,180),(180,600),(600,1500),(1500,3000),(3000,7000),(7000,14000)]:
    sos=signal.butter(3,[lo,hi],btype='bandpass',fs=sr,output='sos')
    band=signal.sosfilt(sos,residual,axis=0)
    reference_band=signal.sosfilt(sos,x,axis=0);osc_band=signal.sosfilt(sos,y,axis=0)
    rho=float(np.clip(np.corrcoef(reference_band[valid].T)[0,1],-.98,.98))
    # Preserve correlation per band with common/independent *new* noise sources.
    u=signal.sosfilt(sos,rng.standard_normal(len(x)))
    v=signal.sosfilt(sos,rng.standard_normal(len(x)))
    u/=max(np.std(u[valid]),1e-12);v/=max(np.std(v[valid]),1e-12)
    n=np.column_stack((u,rho*u+np.sqrt(1-rho*rho)*v))
    a=np.exp(-1/(.012*sr))
    env=np.sqrt(np.maximum(0,signal.lfilter([1-a],[1,-a],band*band,axis=0)))
    # A waveform residual includes phase error. Constrain its noise budget to
    # positive spectral energy missing from the oscillators, instead of filling
    # all phase error with hiss.
    budget=np.maximum(0,np.mean(reference_band[valid]**2,axis=0)-np.mean(osc_band[valid]**2,axis=0))
    env*=np.sqrt(budget/np.maximum(np.mean(env[valid]**2,axis=0),1e-30))
    basis.append(n*env)
    measurements.append(dict(lo=lo,hi=hi,target_band_lr_correlation=rho,positive_energy_budget=budget.tolist(),
        residual_rms_dbfs=float(10*np.log10(np.mean(band[valid]**2)+1e-30))))
bands=[(60,180),(180,600),(600,1500),(1500,3000),(3000,7000),(7000,14000)]
def powers(audio):
    f,p=signal.welch(audio[valid],sr,nperseg=4096,axis=0)
    return np.array([p[(f>=lo)&(f<hi)].sum() for lo,hi in bands])
reference_power=powers(x);osc_power=powers(y)
matrix=np.column_stack([powers(b) for b in basis]);weights=1/np.maximum(reference_power,1e-20)
# Jointly account for overlapping filters and AM sidebands. No addition can
# undo excess oscillator energy, so a band can legitimately receive zero noise.
coefficients=nnls(matrix*weights[:,None],(reference_power-osc_power)*weights)[0]
for b,c in zip(basis,coefficients):stochastic+=b*np.sqrt(c)
outputs={'reference':x,'osc64_per_channel':y,'osc64_plus_residual':y+stochastic}
metrics={}
for key,audio in outputs.items():
    f,p=signal.welch(audio,sr,nperseg=4096,axis=0)
    mid=(audio[:,0]+audio[:,1])/2;side=(audio[:,0]-audio[:,1])/2
    metrics[key]=dict(high_3k_14k_fraction=float(p[(f>=3000)&(f<14000)].sum()/p.sum()),
        side_to_mid_db=float(10*np.log10(np.mean(side[valid]**2)/np.mean(mid[valid]**2))))
    outputs[key]=audio*10**(-23/20)/np.sqrt(np.mean(audio[valid]**2))
gain=min(1,.85/max(abs(v).max() for v in outputs.values()))
for key,audio in outputs.items():
    audio=audio*gain;ramp=np.linspace(0,1,240);audio[:240]*=ramp[:,None];audio[-240:]*=ramp[::-1,None]
    sf.write(out/f'B_{key}_rms_matched.wav',audio,sr,subtype='PCM_24')
report=dict(seed=48271,oscillators='up to 64 tracked trajectories PER CHANNEL',bands=measurements,metrics=metrics,noise_basis_power_coefficients=coefficients.tolist(),
    source='B_cabin_pull.wav, source 218-230 seconds; interior recording, no video available locally',
    scope='Same excerpt offline fit; NOT the C driving engine. Residual includes phase/tracking and transient errors, not only physical noise.',
    processing='Independent stereo oscillator fits; residual reduced to six band energy envelopes and reference band correlation; fresh seeded noise jointly power-fitted with nonnegative least squares to band energy deficits, accounting for overlapping filters; no residual sample playback.',
    audition='Central-window stereo unweighted RMS matched to -23 dBFS then ONE common peak gain, not LUFS; source masters unchanged.')
(out/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(metrics,indent=2))
