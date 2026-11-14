"""Finite source-budget comparison, preserving prior phase/high detail and old audition."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','model','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from research_archive_v1 import load,save,sha
from idle_phase_recipe_v1.phase import spline,phasors
from idle_phase_recipe_v1.render2 import noise
from idle_phase_amplitude_v1.model import nodes,interpolation,native,gains

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},inputs={},renders=[])
def track(path):r['inputs'][str(path)]=sha(path);return path
try:
    names=['tools/render_idle_joint_budget_v1.py','tools/idle_phase_recipe_v1/phase.py','tools/idle_phase_recipe_v1/render2.py',
        'tools/idle_phase_amplitude_v1/model.py','tools/research_archive_v1.py','research/idle_local_partition_v1_audio_plan.json']
    for name in names:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest)
        r['sources'][name]=sha(repo/name)
    model=load(track(a.model/'model.json'));assert model['schema']=='vsl.idle-joint-coherent-residual-budget/1'
    parent=a.workspace/'baselines';prior=parent/'idle_phase_amplitude_v1/evidence/residual_render1'
    previous=load(track(prior/'report.json'));oldlow=load(track(prior/'model.json'))['taps']
    profile=load(track(parent/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json'))
    phase_root=parent/'idle_phase_recipe_v1/evidence/render2';phase_model=load(track(phase_root/'model.json'))
    amplitude_model=load(track(parent/'idle_phase_amplitude_v1/evidence/render2/model.json'));table=interpolation(amplitude_model)
    frames=24*48000;warm=profile['warmup_frames'];count=frames+warm
    selected=[1,2,4];oldamp=np.array(profile['modal']['amplitude_LR'])[selected];newamp=np.array(model['main_amplitude_LR'])
    delta_phase=np.diff(np.array(profile['modal']['initial_phase_LR'])[selected],axis=1)[:,0]
    for row in previous['renders']:
        seed=row['seed'];low_delta=np.zeros((frames,2))
        for j,kernel in enumerate(model['kernels']):
            excitation=noise(seed,j,count,'gaussian');before=profile['kernels'][j]
            old=signal.oaconvolve(excitation,oldlow[j])[warm:count]*before['gain']
            new=signal.oaconvolve(excitation,kernel['taps'])[warm:count]*kernel['gain']
            low_delta+=new[:,None]*[1.,kernel['right_over_left']]-old[:,None]*[1.,before['right_over_left']]
        baseline,rate=sf.read(track(prior/row['files']['mix_0.5']['file']),always_2d=True)
        main,rate=sf.read(track(prior/row['files']['main_0.5']['file']),always_2d=True);assert rate==48000
        with np.load(track(phase_root/f'motion_{seed}.npz')) as f:motion=spline(phase_model,f['coordinate_nodes'])
        values=nodes(amplitude_model,seed,24);xx=np.empty((frames,3));mains={'0.0':main,'0.5':main.copy(),'1.0':main.copy()}
        for start in range(0,frames,24000):
            stop=min(frames,start+24000);t=np.arange(start,stop)/48000;z=phasors(phase_model,motion,t)
            x=native(values,table,start,stop-start);xx[start:stop]=x
            for key,amount in [('0.5',0.),('1.0',1.)]:
                g=gains(x,amount,table['covariance'])
                for c in range(2):
                    contributions=(z*np.exp(1j*delta_phase*c)).real
                    mains[key][start:stop,c]+=np.sum(contributions*(newamp[:,c]*g-oldamp[:,c]),axis=1)
        files={}
        for key in ['0.0','0.5','1.0']:
            mix=baseline if key=='0.0' else baseline+low_delta+mains[key]-main
            for bus,wave in [('mix',mix),('main',mains[key])]:
                assert np.isfinite(wave).all() and abs(wave).max()<.85
                path=a.out/f'{bus}_{key}_{seed}.wav';sf.write(path,wave,48000,subtype='FLOAT')
                files[bus+'_'+key]=dict(file=path.name,sha256=sha(path),peak=float(abs(wave).max()),rms=float(np.sqrt(np.mean(wave**2))))
        trace=a.out/f'nodes_{seed}.npz';np.savez_compressed(trace,nodes=values)
        gain=gains(xx,1.,table['covariance'])
        r['renders'].append(dict(seed=seed,frames=frames,files=files,nodes_file=trace.name,nodes_sha256=sha(trace),
             full_gain_bounds=[float(gain.min()),float(gain.max())],old_baseline_FLOAT_preserved=True))
        save(a.out/'report.json',r);print(dict(seed=seed,peaks={key:v['peak'] for key,v in files.items()}),flush=True)
    r.update(result='finite_idle_joint_budget_pending_audit',new_model_sha256=sha(a.model/'model.json'),
             phase_high_detail_and_other10_unchanged=True,source_pcm_looped=False,runtime_changed=False,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
