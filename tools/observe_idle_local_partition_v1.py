"""Measure selected coherent variation versus independent residual allocation, no new synth."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha
from idle_local_partition_v1.known import run
from idle_local_partition_v1.partition import partition,budget,BANDS
from idle_conditioned_detail_v1.features import phases

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},inputs={},cases=[])
def track(path):r['inputs'][str(path)]=sha(path);return path
def record(label,audio,z,frequencies,metadata):
    output=partition(audio,frequencies,z);budgets={}
    for kind in ['static','dynamic']:
        b=budget(output['audio'],output[kind+'_main'],output[kind+'_residual'],frequencies)
        budgets[kind]={k:v.tolist() if isinstance(v,np.ndarray) else v for k,v in b.items()}
    file=a.out/(label+'.npz');np.savez_compressed(file,original_audio=audio,phasors=z,**output)
    row=dict(label=label,file=file.name,sha256=sha(file),metadata=metadata,budgets=budgets,
             residual_near_line_ratio=(np.array(budgets['dynamic']['residual_near_lines'])/np.array(budgets['static']['residual_near_lines'])).tolist())
    r['cases'].append(row);save(a.out/'report.json',r)
    print(dict(label=label,near_line_residual_ratio=np.array(row['residual_near_line_ratio'])[:,0].tolist()),flush=True)
try:
    names=['tools/observe_idle_local_partition_v1.py','tools/idle_local_partition_v1/partition.py','tools/idle_local_partition_v1/known.py',
        'research/idle_local_partition_v1_plan.json','tools/idle_phase_amplitude_v1/observe.py','tools/idle_phase_amplitude_v1/residual.py',
        'tools/idle_phase_amplitude_v1/known.py','tools/idle_conditioned_detail_v1/features.py','tools/research_archive_v1.py']
    for name in names:
        path=a.out/'exact_sources'/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,path)
        r['sources'][name]=sha(repo/name)
    r['known'],fixtures=run();np.savez_compressed(a.out/'known.npz',**fixtures)
    print(dict(stage='known',results=r['known']['cases']),flush=True)
    parent=a.workspace/'baselines';origin=parent/'idle_conditioned_detail_v1/evidence/observe1'
    profile=load(track(parent/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json'));frequencies=np.array(profile['modal']['frequencies_hz'])
    for seed in [None,149921,277139,381611]:
        for part in ['train','check']:
            with np.load(track(origin/(part+'.npz'))) as f:audio=f['audio'];z=f['phasors']
            if seed is not None:
                fourier=np.fft.rfft(audio,axis=0);angle=np.random.default_rng(seed).uniform(-np.pi,np.pi,len(fourier));angle[0]=angle[-1]=0
                audio=np.fft.irfft(fourier*np.exp(1j*angle[:,None]),n=len(audio),axis=0)
                with np.load(track(origin/f'{part}_phase_{seed}.npz')) as f:z=f['phasors']
            label=('source' if seed is None else 'phase_'+str(seed))+'_'+part
            record(label,audio,z,frequencies,dict(kind='source' if seed is None else 'samePSD_control',part=part,seed=seed))
    generated=parent/'idle_phase_amplitude_v1/evidence/residual_render1'
    report=load(track(generated/'report.json'));assert report['result']=='finite_separated_low_residual_pending_audit'
    for row in report['renders']:
        seed=row['seed']
        for condition in ['0.0','0.5','1.0']:
            path=track(generated/row['files']['mix_'+condition]['file']);audio,rate=sf.read(path,always_2d=True);assert rate==48000
            for block,first in enumerate(range(0,len(audio),144000)):
                part=audio[first:first+144000];z=phases(part[:,0],frequencies[[1,2,4]])
                record(f'generated_{seed}_{condition}_{block}',part,z,frequencies,
                       dict(kind='generated',seed=seed,condition=condition,block=block))
    r.update(result='local_selected_core_partition_observed',bands_hz=BANDS.tolist(),source_cases=8,generated_cases=72,
             ROI_frames=[21600,122400],recorded_trajectory_exported=False,new_synthesis_model=False,runtime_changed=False,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
