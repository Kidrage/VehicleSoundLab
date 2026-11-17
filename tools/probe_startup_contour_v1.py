"""Offline feasibility: two coarse amplitude contours on existing source components."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import numpy as np
import soundfile as sf
from scipy import signal,optimize
from event_authoring.model import randoms,coefficients,attack
from event_authoring.audio import read
from event_authoring.temporal_fit import band_curves
from event_designer.package import write_json


def render(p,curves,seed=27431):
    """Independent experimental law; not yet a realtime parameter document."""
    n=round(p['duration_seconds']*48000);t=np.arange(n)/48000;r=randoms(seed,n+1)
    variations=1+.002*r[0];x=np.zeros(n);noise=np.zeros(n)
    def contour(hz):
        return next((np.interp(t,c['seconds'],c['gain']) for c in curves if c['low_hz']<=hz<c['high_hz']),None)
    for m in p['modes']:
        c=contour(m['hz']);env=c if c is not None else attack(t,m.get('attack_seconds',0))*np.exp(-t/m['decay_seconds'])
        x+=m['amplitude']*env*np.sin(m['phase']+2*np.pi*m['hz']*variations*t)
    for b in p['bands']:
        c=contour(b['hz']);env=c if c is not None else attack(t,b['attack_seconds'])*np.exp(-t/b['decay_seconds'])
        num,den=coefficients(b['hz'],b['q']);noise+=b['amplitude']*env*signal.lfilter(num,den,r[1:])
    if p.get('noise_lowpass_hz',0):noise=signal.sosfilt(signal.butter(4,p['noise_lowpass_hz'],fs=48000,output='sos'),noise)
    x+=noise;env=attack(t,p['attack_seconds']);remaining=np.clip((n-np.arange(n))/(48000*p['release_seconds']),0,1)
    return x*env*remaining**2*(3-2*remaining)*p['level']


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    doc=json.loads(Path('E:/VehicleSoundLab/references/analysis/startup_shape_v1/candidate2/analysis/profile.json').read_text(encoding='utf-8'))
    p=doc['parameters'];source=Path('E:/VehicleSoundLab/references/clean/A_decoded_float.wav')
    raw,rate,provenance=read(source,37.22,38.02);bg,_,background=read(source,35.,36.2)
    t,power=band_curves(raw);_,bp=band_curves(bg);target=np.maximum(power-bp.mean(axis=1)[:,None],0)
    contours=[dict(low_hz=lo,high_hz=hi,seconds=[0.,.025,.06,.12,.25,.45,.65,.8],gain=[1.]*8)
        for lo,hi in ((1200,4500),(4500,14000))]
    scale=np.maximum(target.mean(axis=1),1e-15)
    def parameters(values):
        result=deepcopy(contours)
        for index,c in enumerate(result):c['gain']=values[index*8:index*8+8].tolist()
        return result
    def residual(values):
        _,generated=band_curves(render(p,parameters(values)))
        return ((generated[2:]-target[2:])/scale[2:,None]).ravel()
    # Fixed coarse time grid, max16 amplitude controls; no phase/waveform fitting.
    result=optimize.least_squares(residual,np.ones(16),bounds=(0,8),max_nfev=120,
        ftol=1e-8,xtol=1e-8,gtol=1e-8)
    c=parameters(result.x);rows=[]
    from event_authoring.model import synth
    original=synth(p,seconds=.8)
    sf.write(out/'original.wav',original,rate,subtype='FLOAT');sf.write(out/'reference.wav',raw,rate,subtype='FLOAT')
    for seed in (27431,48271,93931,17389):
        y=render(p,c,seed);sf.write(out/f'candidate-{seed}.wav',y,rate,subtype='FLOAT')
        _,actual=band_curves(y);_,old=band_curves(synth(p,seed=seed,seconds=.8))
        rows.append(dict(seed=seed,band_curve_rmse_before=np.sqrt(np.mean(((old-target)/scale[:,None])**2,axis=1)).tolist(),
            band_curve_rmse_after=np.sqrt(np.mean(((actual-target)/scale[:,None])**2,axis=1)).tolist(),
            mean_power_ratio=(actual.mean(axis=1)/target.mean(axis=1)).tolist(),peak=float(np.max(abs(y)))))
    write_json(out/'report.json',dict(schema='vsl.startup-contour-feasibility/1',profile=doc,contours=c,
        source=provenance,background=background,results=rows,evaluations=result.nfev,
        optimizer_terminated=bool(result.success),rt_implemented=False,timbre_accepted=False,
        limitations='Coarse amplitude laws on existing modes and shaped procedural noise. No carrier, phase, room or waveform fitting; frequency leakage and one recording remain. No physical source identification.'))
    shutil.copy2(__file__,out/'executed_probe.py');print(json.dumps(dict(results=rows,contours=c)),flush=True)


if __name__=='__main__':main()
