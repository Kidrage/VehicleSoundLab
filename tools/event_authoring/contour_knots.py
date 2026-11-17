"""Offline adaptive placement of the existing eight event amplitude controls."""
from copy import deepcopy
import numpy as np
from scipy import optimize
from .model import synth
from .temporal_fit import band_curves
from .contract import validate


def propose(time,power,duration,count=8):
    """Greedily retain the largest amplitude-shape interpolation errors.

    The source observations are Hann-smoothed band powers, not waveform points.
    Endpoints are explicit; knots stay >=10ms apart. The parameter count and
    runtime linear interpolator are unchanged.
    """
    t=np.r_[0.,time,duration];a=np.sqrt(np.maximum(np.r_[power[0],power,power[-1]],0))
    scale=max(float(a.max()),1e-30);a=a/scale
    selected=[0,len(t)-1]
    for _ in range(count-2):
        order=sorted(selected);estimate=np.interp(t,t[order],a[order]);error=(estimate-a)**2
        distance=np.min(abs(t[:,None]-t[order][None,:]),axis=1);error[distance<.01]=-1
        index=int(np.argmax(error))
        if error[index]<0:break
        selected.append(index)
    return t[sorted(selected)].tolist()


def fit_shape(profile,target,duration,rows,adaptive_indices=None,weights=None,band_offset=2):
    p=deepcopy(profile);time=np.arange(target.shape[1])*.005+1024/48000
    selected=[(k+band_offset,row) for k,row in enumerate(rows) if row['selected']]
    prior=p.get('contours',[]);p['contours']=[]
    for k,row in selected:
        old=next((c for c in prior if [c['low_hz'],c['high_hz']]==row['hz']),None)
        times=propose(time,target[k],duration) if adaptive_indices is None or k in adaptive_indices else old['seconds'].copy()
        gains=np.interp(times,old['seconds'],old['gain']).tolist() if old else [1.]*len(times)
        p['contours'].append(dict(low_hz=row['hz'][0],high_hz=row['hz'][1],seconds=times,gain=gains))
    indices=[k for k,_ in selected];sizes=[len(c['gain']) for c in p['contours']]
    initial=np.concatenate([c['gain'] for c in p['contours']])
    reference=target[indices]/np.maximum(target[indices].mean(axis=1),1e-30)[:,None]
    weight=np.ones((len(indices),1)) if weights is None else np.asarray(weights)[:,None]
    def assign(g):
        start=0
        for c,n in zip(p['contours'],sizes):c['gain']=g[start:start+n].tolist();start+=n
    def residual(g):
        assign(g);_,power=band_curves(synth(p,seconds=duration));power=power[indices]
        return ((power/np.maximum(power.mean(axis=1),1e-30)[:,None]-reference)*weight).ravel()
    result=optimize.least_squares(residual,initial,bounds=(0,8),max_nfev=80,ftol=1e-8,xtol=1e-8,gtol=1e-8)
    assign(result.x)
    return validate(p),dict(evaluations=result.nfev,optimizer_terminated=bool(result.success),
        seconds=[c['seconds'] for c in p['contours']],method='greedy-eight-knots-v1')
