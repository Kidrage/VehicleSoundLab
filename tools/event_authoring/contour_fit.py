"""Optional coarse high-band amplitude contours on the existing event components."""
from copy import deepcopy
import numpy as np
from scipy import optimize
from .model import synth
from .temporal_fit import band_curves
from .contract import validate


def fit(profile,x,background):
    p=deepcopy(profile);duration=len(x)/48000
    t,raw=band_curves(x);_,bg=band_curves(background);target=np.maximum(raw-bg.mean(axis=1)[:,None],0)
    if len(t)<16:raise ValueError('多段包络需要至少16帧分析数据，请使用更长的单次动作片段')
    # Eight coarse knots per group; not an audio-rate envelope or waveform table.
    times=(duration*np.array([0,.03125,.075,.15,.3125,.5625,.8125,1.])).tolist()
    p['contours']=[dict(low_hz=lo,high_hz=hi,seconds=times.copy(),gain=[1.]*8)
        for lo,hi in ((1200.,4500.),(4500.,14000.))]
    scale=np.maximum(target[2:].mean(axis=1),1e-12)
    def assign(g):
        for i,c in enumerate(p['contours']):c['gain']=g[i*8:(i+1)*8].tolist()
    def residual(g):
        assign(g);y=synth(p,seconds=duration);_,power=band_curves(y)
        return ((power[2:]-target[2:])/scale[:,None]).ravel()
    initial=residual(np.ones(16))
    result=optimize.least_squares(residual,np.ones(16),bounds=(0,8),max_nfev=80,
        ftol=1e-8,xtol=1e-8,gtol=1e-8)
    final=residual(result.x);assign(result.x)
    return validate(p),dict(method='band-contour-v1',seed=27431,evaluations=result.nfev,
        optimizer_terminated=bool(result.success),initial_scaled_rmse=float(np.sqrt(np.mean(initial**2))),
        fitted_scaled_rmse=float(np.sqrt(np.mean(final**2))),
        policy='Two nominal-frequency groups1200–4500/4500–14000Hz,8 fixed relative-time linear amplitude knots each,nonnegative gain0..8. Fit actual finite synthetic band-power curves,explicit2048 Hann/hop240 and fixed background subtraction; same modal frequencies/phases and procedural noise. Afterwards recalibrate and check all six spectral bands with original gates.',
        limitations='Contour replaces the selected components attack/decay, not the global envelope or release; time follows request decay, pitch does not change membership. One crop/fit seed and band-power agreement do not prove mechanical identity, physical source isolation or naturalness. Coarse contours do not retain waveform or rapid microstructure.')
