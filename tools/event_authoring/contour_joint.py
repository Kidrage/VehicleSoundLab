"""Opt-in reliable-band contours and amplitude-independent spectral calibration."""
from copy import deepcopy
import numpy as np
from scipy import optimize
from .model import synth
from .temporal_fit import band_curves
from .response_basis import calibrate_unit
from .contract import validate


def observations(x,background):
    t,raw=band_curves(x);_,bg=band_curves(background)
    if len(t)<16:raise ValueError('多段包络需要至少16帧分析数据，请使用更长的单次动作片段')
    noise=bg.mean(axis=1)
    contrast=10*np.log10(np.maximum(raw.mean(axis=1),1e-30)/np.maximum(noise,1e-30))
    target=np.maximum(raw-noise[:,None],0)
    rows=[dict(hz=[lo,hi],contrast_db=float(contrast[k]),selected=bool(contrast[k]>=3),
        reason='At least3dB band event/background contrast' if contrast[k]>=3 else 'Band contrast below3dB; retain original local envelopes')
        for k,(lo,hi) in enumerate(((60,300),(300,1200),(1200,4500),(4500,14000))) if k>=2]
    return t,target,rows


def shape_errors(profile,target,duration,indices):
    _,power=band_curves(synth(profile,seconds=duration))
    normalized=power/np.maximum(power.mean(axis=1),1e-30)[:,None]
    reference=target/np.maximum(target.mean(axis=1),1e-30)[:,None]
    errors=np.sqrt(np.mean((normalized-reference)**2,axis=1))
    return [float(errors[k]) for k in indices]


def fit_shape(profile,target,duration,rows,band_offset=2,weights=None):
    p=deepcopy(profile);times=(duration*np.array([0,.03125,.075,.15,.3125,.5625,.8125,1.])).tolist()
    selected=[(k+band_offset,row) for k,row in enumerate(rows) if row['selected']]
    previous=p.get('contours',[])
    p['contours']=[dict(low_hz=r['hz'][0],high_hz=r['hz'][1],seconds=times.copy(),
        gain=next((c['gain'].copy() for c in previous if c['low_hz']==r['hz'][0] and c['high_hz']==r['hz'][1] and c['seconds']==times),[1.]*8))
        for _,r in selected]
    initial=np.array([g for c in p['contours'] for g in c['gain']]);indices=[k for k,_ in selected]
    reference=target[indices]/np.maximum(target[indices].mean(axis=1),1e-30)[:,None]
    def assign(g):
        for i,c in enumerate(p['contours']):c['gain']=g[i*8:(i+1)*8].tolist()
    def residual(g):
        assign(g);_,power=band_curves(synth(p,seconds=duration));power=power[indices]
        normalized=power/np.maximum(power.mean(axis=1),1e-30)[:,None]
        residual=normalized-reference
        if weights is not None:residual*=np.asarray(weights)[:,None]
        return residual.ravel()
    result=optimize.least_squares(residual,initial,bounds=(0,8),max_nfev=80,ftol=1e-8,xtol=1e-8,gtol=1e-8)
    assign(result.x)
    return validate(p),dict(evaluations=result.nfev,optimizer_terminated=bool(result.success))


def fit(profile,x,background,arrays):
    duration=len(x)/48000;t,target,rows=observations(x,background)
    indices=[k+2 for k,row in enumerate(rows) if row['selected']]
    if not indices:
        return deepcopy(profile),dict(method='band-contour-v2',bands=rows,selected_attempt=None,
            qualified=False,reason='No upper band has3dB event/background contrast'),None
    baseline=shape_errors(profile,target,duration,indices)
    p=deepcopy(profile);attempts=[];candidates=[]
    for step in range(2):
        p,shape=fit_shape(p,target,duration,rows)
        p,response=calibrate_unit(p,arrays,duration)
        errors=shape_errors(p,target,duration,indices)
        temporal=all(a<=b+1e-10 for a,b in zip(errors,baseline))
        qualified=bool(response['qualified'] and temporal)
        attempts.append(dict(step=step,shape=shape,response=response,shape_rmse=errors,
                             temporal_nonregression=temporal,qualified=qualified))
        candidates.append((not qualified,float(np.mean(np.square(errors))),step,deepcopy(p),response))
    _,_,choice,p,response=min(candidates,key=lambda row:(row[0],row[1],row[2]))
    report=dict(method='band-contour-v2',seed=27431,bands=rows,baseline_shape_rmse=baseline,
        selected_attempt=choice,qualified=attempts[choice]['qualified'],attempts=attempts,
        policy='Only upper bands with >=3dB mean band event/background contrast receive8 coarse knots. Fit mean-normalized power-curve shape, then unit-amplitude existing-component finite-response gains; two bounded alternations, choose qualified lowest shape error. Original six spectral gates and per-selected-band temporal nonregression both required.',
        limitations='A low-contrast band keeps its original local envelopes, not an inferred silent or isolated source. Spectral positive-bin excess and band-total temporal excess differ; shape fitting does not treat them as identical energy targets. One fit seed/crop does not establish naturalness, physical RPM or source identity. Runtime components/counts remain unchanged.')
    return validate(p),report,response
