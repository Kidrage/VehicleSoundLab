"""Fixed-source experiment: constrain event spectrum and contour shape together."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

import numpy as np
from scipy import optimize
import soundfile as sf

from event_authoring.contour_all_bands import observations
from event_authoring.contour_joint import shape_errors
from event_authoring.contour_knots import propose
from event_authoring.contour_response import QuadraticResponse
from event_authoring.measure import observe
from event_authoring.model import synth
from event_authoring.response_fit import EDGES
from event_authoring.temporal_fit import band_curves
from research_archive_v1 import load, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, out/'executed_probe.py')
    root = Path('E:/VehicleSoundLab/references/analysis/A_exterior_startup_v1')
    x, _ = sf.read(root/'selection1/later-original.wav', always_2d=True)
    background, _ = sf.read(root/'selection1/background-original.wav', always_2d=True)
    entry = load(root/'catch1/refused-fit.json')
    _, arrays = observe(x, background)
    time, target, rows = observations(x, background)
    duration = len(x)/48000
    indices = [k for k, row in enumerate(rows) if row['selected']]
    baseline = shape_errors(entry, target, duration, indices)
    reference = target[indices]/np.maximum(target[indices].mean(axis=1),1e-30)[:,None]
    weights = 1/np.maximum(baseline,.05)
    f,p,bg,*_ = arrays
    excess = np.maximum(p-bg,0)
    spectral = np.array([excess[(f>=lo)&(f<hi)].sum()*(f[1]-f[0]) for lo,hi in EDGES])
    floor = spectral.sum()*1e-6
    report = dict(baseline=baseline, results={}, goal_complete=False)
    for layout in ('fixed','adaptive'):
        p = deepcopy(entry)
        p['contours'] = [dict(low_hz=row['hz'][0], high_hz=row['hz'][1], gain=[1.]*8,
            seconds=(propose(time,target[k],duration) if layout=='adaptive' else
                (duration*np.array([0,.03125,.075,.15,.3125,.5625,.8125,1.])).tolist()))
            for k,row in enumerate(rows) if row['selected']]
        response = QuadraticResponse(p,duration)
        def assign(g):
            offset=0
            for contour,size in zip(p['contours'],response.sizes):
                contour['gain']=g[offset:offset+size].tolist();offset+=size
        initial=np.ones(response.count)
        direct=synth(p,seconds=duration)
        np.testing.assert_allclose(response.waveform(initial),direct,rtol=2e-12,atol=2e-14)
        _, actual=band_curves(direct)
        np.testing.assert_allclose(response.power(response.temporal,initial),actual,rtol=2e-11,atol=2e-15)
        spectral_weight=np.sqrt(reference.size/6)
        def residual(g):
            power=response.power(response.temporal,g)[indices]
            shape=(power/np.maximum(power.mean(axis=1),1e-30)[:,None]-reference)*weights[:,None]
            mean=response.power(response.spectral,g)
            energy=(np.log(np.maximum(mean,0)+floor)-np.log(spectral+floor))*spectral_weight
            return np.r_[shape.ravel(),energy]
        def jacobian(g):
            power=response.power(response.temporal,g)[indices]
            derivative=response.derivative(response.temporal,g)[indices]
            mean=np.maximum(power.mean(axis=1),1e-30)
            jac=(derivative/mean[:,None,None]-power[:,:,None]*derivative.mean(axis=1)[:,None,:]/mean[:,None,None]**2)*weights[:,None,None]
            energy=response.power(response.spectral,g)
            spectral_jac=response.derivative(response.spectral,g)/(np.maximum(energy,0)+floor)[:,None]*spectral_weight
            return np.concatenate((jac.reshape(-1,response.count),spectral_jac))
        delta=np.linspace(-.4,.4,response.count)
        eps=1e-5
        numeric=(residual(initial+eps*delta)-residual(initial-eps*delta))/(2*eps)
        analytic=jacobian(initial)@delta
        np.testing.assert_allclose(numeric,analytic,rtol=2e-6,atol=2e-7)
        result=optimize.least_squares(residual,initial,jac=jacobian,bounds=(0,8),max_nfev=160,
            ftol=1e-9,xtol=1e-9,gtol=1e-9)
        assign(result.x)
        wave=synth(p,seconds=duration)
        _,spectrum=__import__('event_authoring.measure',fromlist=['spectrum']).spectrum(wave[:,None])
        bands=[]
        for (lo,hi),objective in zip(EDGES,spectral):
            generated=float(spectrum[(f>=lo)&(f<hi)].sum()*(f[1]-f[0]))
            error=float(10*np.log10(max(generated,1e-30)/max(objective,1e-30)))
            passed=abs(error)<=3 if objective>=spectral.sum()*1e-4 else generated<=max(objective*2,spectral.sum()*2e-4)
            bands.append(dict(hz=[lo,hi],error_db=error,passed=bool(passed)))
        errors=shape_errors(p,target,duration,indices)
        qualified=all(b['passed'] for b in bands) and all(a<=b+1e-10 for a,b in zip(errors,baseline))
        save(out/(layout+'.json'),p)
        sf.write(out/(layout+'.wav'),wave,48000,subtype='FLOAT')
        report['results'][layout]=dict(shape_rmse=errors,bands=bands,evaluations=result.nfev,
            optimizer_terminated=bool(result.success),qualified=qualified,peak=float(np.max(abs(wave))))
        save(out/'report.json',report)
        print(layout,report['results'][layout],flush=True)


if __name__=='__main__':
    main()
