"""Audit sparse sample grids and diagnose source suitability without refitting."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from drive_evidence_v1.sources import sha
from sustain_osc_v1.oracle import Gaussian
from idle_modal_v1.modal import peaks

def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',contexts=[])
try:
    shutil.copy2(__file__,a.out/'executed_audit.py')
    parent=load(a.input/'report.json');mp=load(repo/'research/idle_modal_v1_plan.json')
    indices=np.array([0,1,959,960,8191,20003,20004,48000,288000,575999])
    for context in parent['contexts']:
        folder=a.input/context['id'];model=load(folder/'profile.json');evidence=load(folder/'fit_evidence.json')
        train,rate=sf.read(folder/'training.wav',always_2d=True);assert rate==48000
        local=dict(mp,modal_band_hz=[30,120])
        inventories=[peaks(train[j:j+24000],48000,local).tolist() for j in range(0,len(train)-24000+1,12000)]
        # Entire fixed low-band inventory is retained, with no forced path or resampling.
        measured=[]
        for j in range(0,len(train)-24000+1,12000):
            hz,psd=signal.periodogram(train[j:j+24000,0],48000,window='hann',detrend=False)
            mask=(hz>=30)&(hz<120);measured.append(float(psd[mask].sum()*2))
        f=np.asarray(model['modal']['frequencies_hz']);amps=np.array(model['modal']['amplitude_LR']);phase=np.array(model['modal']['initial_phase_LR'])
        expected_main=sum(amps[k]*np.cos(2*np.pi*f[k]*indices[:,None]/48000+phase[k]) for k in range(len(f)))
        errors=[]
        for seed in [149921,277139,381611]:
            env=model['envelope'];cov=np.asarray(env['covariance']);l=np.linalg.cholesky(cov)
            count=575999//env['hop_frames']+2
            rng=Gaussian(seed^0xD1B54A32D192ED03)
            normals=np.array([rng.next() for _ in range(count*len(cov))]).reshape(count,len(cov))
            states=np.empty_like(normals);states[0]=l@normals[0]
            for k in range(1,count):states[k]=env['alpha']*states[k-1]+np.sqrt(1-env['alpha']**2)*(l@normals[k])
            expected={method:expected_main.copy() for method in ['fine','dynamic']}
            for i,kernel in enumerate(model['kernels']):
                rng=Gaussian(seed^(0x9E3779B97F4A7C15*(i+1)&((1<<64)-1)))
                noise=np.array([rng.next() for _ in range(576000+model['warmup_frames'])])
                taps=np.asarray(kernel['taps']);values=[]
                for sample in indices:
                    at=sample+model['warmup_frames']
                    values.append(float(np.dot(taps,noise[at-np.arange(len(taps))]))*kernel['gain'])
                values=np.array(values)[:,None]*np.array([[1.,kernel['right_over_left']]])
                hop=env['hop_frames'];cell=indices//hop;u=(1-np.cos(np.pi*(indices%hop)/hop))/2
                interpolated=(1-u)*states[cell,i]+u*states[cell+1,i]
                variance=cov[i,i]*((1-u)**2+u*u+2*env['alpha']*u*(1-u))
                gains=np.exp(env['strength']*interpolated-env['strength']**2*variance)
                expected['fine']+=values;expected['dynamic']+=values*gains[:,None]
            for method in expected:
                y,rate=sf.read(folder/f'{method}_{seed}.wav',always_2d=True)
                assert rate==48000 and y.shape==(576000,2) and np.isfinite(y).all()
                error=float(abs(y[indices]-expected[method]).max())
                # FLOAT quantization absolute bound depends on actual represented values.
                bound=float(max(2**-24*abs(expected[method]).max(),2**-149)+1e-11)
                assert error<=bound,(context['id'],method,error,bound)
                errors.append(dict(seed=seed,method=method,selected_sample_error=error,float_bound=bound,
                    peak=float(abs(y).max()),samples_above_fullscale=int(np.count_nonzero(abs(y)>1))))
        target=np.asarray(evidence['training_power_LR']);main=np.asarray(evidence['modal_power_LR'])
        info=dict(id=context['id'],modes=len(f),lowest_modal_hz=float(f.min()),
            low_modal_power_fraction=(main[0]/target[0]).tolist(),
            low_training_power_fraction=(target[0]/target.sum(axis=0)).tolist(),
            low_window_inventories_hz=inventories,low_window_power_L=measured,
            selected_sample_grid=indices.tolist(),errors=errors,
            timbre_accepted=False,full_RPM_coverage=False)
        if context['id']=='A_exterior_low_rev':
            assert np.count_nonzero((f>=30)&(f<120))==0
            info['decision']='Do not promote A to a usable source. Stable-mode selection omitted all low modes; residual tails approximate their power and do not recover a mechanical low voice. Preserve failed portability attempt, no threshold/window/band sweep.'
        else:
            assert all(row['frozen_F2_samples_exact'] for row in context['seeds'])
            info['decision']='Generic kernel preserves all frozen F2 FLOAT samples exactly; existing listening request remains pending.'
        r['contexts'].append(info)
        print(json.dumps(dict(stage='context_checked',id=info['id'],decision=info['decision'])),flush=True)
    r.update(result='generic_F2_identity_verified_A_portability_not_qualified',
        input_report_sha256=sha(a.input/'report.json'),runtime_changed=False,
        audit_scope='Direct scalar/cosine and FIR sums on10predeclared sample positions per rendered file, not complete A sample replay. Full F2 files additionally match frozen outputs exactly.',
        next='A source requires a source-supported changing-frequency representation; do not fill omitted tonal low energy with stronger random rumble or relax support to make it pass.')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
