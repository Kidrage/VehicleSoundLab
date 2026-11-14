"""Finite learned local response, preserving original sparse source and all zero audio."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','fit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from research_archive_v1 import load,save,sha
from idle_phase_difference_v1.features import matrix
from idle_positive_power_v1.model import predict as q_predict
from idle_phase_recipe_v1.phase import spline,phasors
from idle_phase_recipe_v1.render2 import phase_audio,noise
from idle_local_shape_v1.model import predict
from idle_local_shape_v1.filterbank import compile_bank,gain,known

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},inputs={},renders=[])
def track(path):r['inputs'][str(path)]=sha(path);return path
try:
    names=['tools/render_idle_local_shape_v1.py','tools/idle_local_shape_v1/model.py','tools/idle_local_shape_v1/filterbank.py',
           'tools/research_archive_v1.py','research/idle_local_shape_v1_plan.json','research/idle_local_shape_v1_audio_plan.json',
           'tools/idle_phase_difference_v1/features.py','tools/idle_positive_power_v1/model.py',
           'tools/idle_phase_recipe_v1/phase.py','tools/idle_phase_recipe_v1/render2.py','tools/idle_modal_v1/modal.py']
    for name in names:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest)
        r['sources'][name]=sha(repo/name)
    r['known']=known();print(dict(stage='known',result=r['known']),flush=True)
    fit=load(track(a.fit/'report.json'));assert fit['result']=='local_positive_shape_extraction_complete'
    models=[row['model'] for row in fit['observations'][0]['bands'][:2]]
    assert all(row['assessment']['check']['improvement']>0 and row['model']['optimizer_success']
               for row in fit['observations'][0]['bands'][:2])
    parent=a.workspace/'baselines';phase_root=parent/'idle_phase_recipe_v1/evidence/render2'
    phase_model=load(track(phase_root/'model.json'))
    profile=load(track(parent/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json'))
    allocation=load(track(parent/'idle_post_budget_v1/evidence/observe1/report.json'))['allocation']
    with np.load(track(a.fit/'source_train.npz')) as f:
        banks=[compile_bank(profile['kernels'][b+2]['taps'],f['bins_'+str(b)]*48000/256) for b in range(2)]
    for b,bank in enumerate(banks):np.savez_compressed(a.out/f'bank_{b}.npz',**bank)
    frames=24*48000;warm=profile['warmup_frames'];law=fit['law']
    for seed in [149921,277139,381611]:
        with np.load(track(phase_root/f'motion_{seed}.npz')) as f:values=f['coordinate_nodes']
        motion=spline(phase_model,values)
        _,main=phase_audio(profile,phase_model,motion,frames,48000)
        details={str(v):np.zeros_like(main) for v in [0.,.5,1.]}
        traces={};q=np.empty((frames,4));probabilities=[np.empty((frames,len(m['prior']))) for m in models]
        for start in range(0,frames,24000):
            stop=min(frames,start+24000);t=np.arange(start,stop)/48000
            feature=matrix(phasors(phase_model,motion,t),hop=1,trim=0)
            q[start:stop]=q_predict(law,feature)
            for b,model in enumerate(models):probabilities[b][start:stop]=predict(model,feature)
        for index,kernel in enumerate(profile['kernels']):
            selected=index in [2,3];delay=banks[index-2]['delay_frames'] if selected else 0
            count=frames+warm+delay
            if index<2:excitation=noise(seed,index,count,'gaussian')
            else:
                p=allocation['probability'][index-2]
                u=noise(seed,index,count,'uniform');normal=noise(seed,index,count,'normal')
                excitation=np.where(u<p,normal/np.sqrt(p),0.)
            original=signal.oaconvolve(excitation,kernel['taps'])[warm:warm+frames]*kernel['gain']
            ratio=np.array([1.,kernel['right_over_left']]);root=np.sqrt(q[:,index-2]) if index>=2 else np.ones(frames)
            if not selected:
                for detail in details.values():detail+=original[:,None]*root[:,None]*ratio
                continue
            b=index-2;bank=banks[b]
            branch=np.column_stack([signal.oaconvolve(excitation,h)[warm+delay:warm+delay+frames]*kernel['gain']
                                    for h in bank['taps']])
            assert abs(branch.sum(axis=1)-original).max()<1e-13
            traces[f'branches_{b}']=branch;traces[f'probabilities_{b}']=probabilities[b]
            traces[f'original_{b}']=original
            for amount in [0.,.5,1.]:
                if amount==0.:y=original
                else:
                    g=gain(probabilities[b],models[b]['prior'],amount,bank['gram'],bank['reference_variance'])
                    traces[f'gain_{b}_{amount}']=g;y=np.einsum('ti,ti->t',g,branch)
                details[str(amount)]+=y[:,None]*root[:,None]*ratio
        row=dict(seed=seed,seconds=24,files={})
        buses={'main':main}
        for amount,detail in details.items():buses['detail_'+amount]=detail;buses['mix_'+amount]=main+detail
        for name,y in buses.items():
            assert np.isfinite(y).all() and abs(y).max()<1.,(name,'No automatic peak normalization')
            path=a.out/f'{name}_{seed}.wav';sf.write(path,y,48000,subtype='FLOAT')
            row['files'][name]=dict(file=path.name,sha256=sha(path),peak=float(abs(y).max()))
        traces['q']=q;path=a.out/f'traces_{seed}.npz';np.savez_compressed(path,**traces)
        before,rate=sf.read(track(phase_root/f'relation_full_{seed}.wav'),frames=frames,always_2d=True)
        zero,_=sf.read(a.out/row['files']['mix_0.0']['file'],always_2d=True)
        error=float(abs(before-zero).max());assert rate==48000 and error<=3e-8
        row.update(trace=path.name,trace_sha256=sha(path),zero_frozen_error_FS=error)
        r['renders'].append(row);save(a.out/'report.json',r)
        print(dict(stage='rendered',seed=seed,zero_frozen_error_FS=error),flush=True)
    r.update(result='finite_local_shape_audio_pending_audit',models=models,selected_bands=[0,1],
             selection_used_previously_inspected_CHECK=True,seconds_each=24,amounts=[0.,.5,1.],
             source_trajectory_replayed=False,runtime_changed=False,listening_accepted=False,
             all_original_innovations_probabilities_and_6FIRs_retained=True,
             branch_internal_lookahead_frames=16384,external_input_latency_qualified=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
