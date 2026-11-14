"""Test cross-portion local spectral shape; preserve failed models too."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha
from idle_local_shape_v1.model import known,fit,assessment
from idle_local_shape_v1.observe import observe,BANDS,FREQUENCIES,CENTERS

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},inputs={},observations=[])
def track(path):r['inputs'][str(path)]=sha(path);return path
try:
    names=['tools/fit_idle_local_shape_v1.py','tools/idle_local_shape_v1/model.py','tools/idle_local_shape_v1/observe.py',
           'tools/idle_positive_power_v1/model.py','tools/idle_phase_difference_v1/features.py',
           'research/idle_local_shape_v1_plan.json','tools/research_archive_v1.py']
    for name in names:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest)
        r['sources'][name]=sha(repo/name)
    r['known']=known();print(dict(stage='known',result=r['known']),flush=True)
    parents=a.workspace/'baselines'
    law=load(track(parents/'idle_positive_power_v1/evidence/observe1/report.json'))['observations'][0]['models']['expanded']
    origin=parents/'idle_conditioned_detail_v1/evidence/observe1'
    for seed in [None,149921,277139,381611]:
        data={};label='source' if seed is None else 'phase_'+str(seed)
        for part in ['train','check']:
            with np.load(track(origin/(part+'.npz'))) as f:audio=f['audio'];z=f['phasors']
            if seed is not None:
                spectrum=np.fft.rfft(audio,axis=0);phase=np.random.default_rng(seed).uniform(-np.pi,np.pi,len(spectrum));phase[0]=phase[-1]=0
                audio=np.fft.irfft(spectrum*np.exp(1j*phase[:,None]),n=len(audio),axis=0)
                with np.load(track(origin/f'{part}_phase_{seed}.npz')) as f:z=f['phasors']
            feature,shapes,sos,bins=observe(audio,z,law);data[part]=(feature,shapes)
            path=a.out/f'{label}_{part}.npz'
            np.savez_compressed(path,feature=feature,sos=sos,centers=CENTERS,
                                **{f'shape_{b}':v for b,v in enumerate(shapes)},
                                **{f'bins_{b}':v for b,v in enumerate(bins)})
        row=dict(seed=seed,label=label,bands=[])
        for b,band in enumerate(BANDS):
            model=fit(data['train'][0],data['train'][1][b])
            result=dict(band_hz=band,model=model,assessment={part:assessment(model,v[0],v[1][b]) for part,v in data.items()})
            row['bands'].append(result)
            print(dict(stage='fit',seed=seed,band=b,success=model['optimizer_success'],
                       check_improvement=result['assessment']['check']['improvement']),flush=True)
        r['observations'].append(row);save(a.out/'report.json',r)
    r.update(result='local_positive_shape_extraction_complete',law=law,window_frames=256,hop_frames=96,
             sample_rate=48000,check_used_for_fit=False,new_audio_generated=False,runtime_changed=False,
             source_trajectory_exported=False,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
