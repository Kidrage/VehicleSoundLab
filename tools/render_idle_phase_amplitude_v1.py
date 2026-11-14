"""Finite phase-aware idle amplitude comparison, original phase/detail retained."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','observer-audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from research_archive_v1 import load,save,sha
from idle_phase_amplitude_v1.model import fit,known,nodes,interpolation,native,gains,covariance
from idle_phase_recipe_v1.phase import spline,phasors
from idle_phase_recipe_v1.render2 import phase_audio,noise
from idle_phase_difference_v1.features import matrix
from idle_positive_power_v1.model import predict

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},inputs={},renders=[])
def track(path):r['inputs'][str(path)]=sha(path);return path
try:
    names=['tools/render_idle_phase_amplitude_v1.py','tools/idle_phase_amplitude_v1/model.py',
           'tools/idle_phase_recipe_v1/phase.py','tools/idle_phase_recipe_v1/render2.py','tools/idle_modal_v1/modal.py',
           'tools/idle_phase_difference_v1/features.py','tools/idle_positive_power_v1/model.py',
           'research/idle_phase_amplitude_v1_audio_plan.json','tools/research_archive_v1.py']
    for name in names:
        path=a.out/'exact_sources'/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,path)
        r['sources'][name]=sha(repo/name)
    assert load(track(a.observer_audit/'report.json'))['result']=='passed'
    observation=load(track(a.input/'report.json'));assert observation['result']=='phase_aware_idle_amplitude_observed'
    r['known']=known();print(dict(stage='known',result=r['known']),flush=True)
    with np.load(track(a.input/'source_train.npz')) as f:model=fit(f['aware_log'])
    save(a.out/'model.json',model);table=interpolation(model)
    np.savez_compressed(a.out/'interpolation.npz',**table)
    r.update(model_sha256=sha(a.out/'model.json'),table_sha256=sha(a.out/'interpolation.npz'))
    parent=a.workspace/'baselines';phase_root=parent/'idle_phase_recipe_v1/evidence/render2'
    phase_model=load(track(phase_root/'model.json'))
    profile=load(track(parent/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json'))
    budget=load(track(parent/'idle_post_budget_v1/evidence/observe1/report.json'))
    law=load(track(parent/'idle_local_shape_v1/evidence/fit1/report.json'))['law']
    probability=budget['allocation']['probability'];frames=24*48000;warm=profile['warmup_frames']
    amplitude=np.array(profile['modal']['amplitude_LR'])[[1,2,4]]
    delta=np.diff(np.array(profile['modal']['initial_phase_LR'])[[1,2,4]],axis=1)[:,0]
    for seed in [149921,277139,381611]:
        with np.load(track(phase_root/f'motion_{seed}.npz')) as f:motion=spline(phase_model,f['coordinate_nodes'])
        _,baseline=phase_audio(profile,phase_model,motion,frames,48000)
        mains={str(s):baseline.copy() for s in [0.,.5,1.]}
        values=nodes(model,seed,24);x=np.empty((frames,3));q=np.empty((frames,4));bounds={}
        for start in range(0,frames,24000):
            stop=min(frames,start+24000);t=np.arange(start,stop)/48000;z=phasors(phase_model,motion,t)
            xx=native(values,table,start,stop-start);x[start:stop]=xx
            q[start:stop]=predict(law,matrix(z,hop=1,trim=0))
            for s in [.5,1.]:
                g=gains(xx,s,table['covariance'])
                for c in range(2):mains[str(s)][start:stop,c]+=((g-1)*(z*np.exp(1j*delta*c)).real)@amplitude[:,c]
        detail=np.zeros_like(baseline);count=warm+frames
        for index,kernel in enumerate(profile['kernels']):
            if index<2:excitation=noise(seed,index,count,'gaussian')
            else:
                p0=probability[index-2];u=noise(seed,index,count,'uniform');n=noise(seed,index,count,'normal')
                excitation=np.where(u<p0,n/np.sqrt(p0),0.)
            y=signal.oaconvolve(excitation,kernel['taps'])[warm:count]*kernel['gain']
            if index>=2:y*=np.sqrt(q[:,index-2])
            detail+=y[:,None]*[1.,kernel['right_over_left']]
        # Prior frozen phase recipe FLOAT must match sample-for-sample after FLOAT conversion.
        frozen,rate=sf.read(track(phase_root/f'relation_full_{seed}.wav'),always_2d=True)
        zero=baseline+detail;zero_error=float(abs(zero.astype(np.float32).astype(float)-frozen[:frames]).max())
        assert rate==48000 and zero_error<=3e-8,(seed,zero_error)
        files={}
        for s in [0.,.5,1.]:
            key=str(s);gg=gains(x,s,table['covariance']);bounds[key]=[float(gg.min()),float(gg.max())]
            for bus,wave in [('main',mains[key]),('mix',mains[key]+detail)]:
                assert np.isfinite(wave).all() and abs(wave).max()<.85
                path=a.out/f'{bus}_{key}_{seed}.wav';sf.write(path,wave,48000,subtype='FLOAT')
                files[bus+'_'+key]=dict(file=path.name,sha256=sha(path),peak=float(abs(wave).max()),rms=float(np.sqrt(np.mean(wave**2))))
        trace=a.out/f'trace_{seed}.npz';np.savez_compressed(trace,nodes=values,native_log=x,q=q)
        curves=covariance(model['taps']);short=x.reshape(-1,960,3).mean(axis=1)
        short-=short.mean(axis=0)
        empirical=np.array([short[:len(short)-k].T@short[k:]/(len(short)-k) for k in range(51)])
        change=mains['1.0']-mains['0.0']
        row=dict(seed=seed,frames=frames,files=files,trace=trace.name,trace_sha256=sha(trace),zero_frozen_error_FS=zero_error,
                 gain_bounds=bounds,empirical_native_covariance=(x.T@x/frames).tolist(),
                 empirical_20msmean_covariance_lags=empirical.tolist(),
                 change_relative_mix_dB=float(20*np.log10(np.linalg.norm(change)/np.linalg.norm(zero))))
        r['renders'].append(row);save(a.out/'report.json',r)
        print(dict(stage='audio',seed=seed,zero_error=zero_error,gain_bounds=bounds,change_dB=row['change_relative_mix_dB']),flush=True)
    r.update(result='finite_phase_aware_amplitude_audio_pending_audit',check_used_for_fit=False,
             phase_amplitude_coupling_identified=False,runtime_changed=False,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
