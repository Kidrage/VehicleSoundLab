"""Generate qualified-for-review optional idle audio, not new defaults or C acceptance."""
import argparse
import shutil
import sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for name in ['workspace','fit','out']:p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from research_archive_v1 import load,save,sha
from idle_phase_recipe_v1.phase import known,coordinates,H
from idle_phase_recipe_v1.render2 import synthesis_frame,render,METHODS
from idle_phase_recipe_v1.spectral import fit as spectral_fit, known as spectral_known

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},inputs={},renders=[])
try:
    names=['tools/run_idle_phase_spectral_recipe_v1.py','tools/idle_phase_recipe_v1/phase.py',
      'tools/idle_phase_recipe_v1/render2.py','tools/idle_modal_v1/modal.py',
      'tools/idle_phase_difference_v1/features.py','tools/idle_positive_power_v1/model.py',
      'tools/research_archive_v1.py','research/idle_phase_recipe_v1_plan.json', 'research/idle_phase_recipe_v1_spectral_extension.json', 'tools/idle_phase_recipe_v1/spectral.py']
    for name in names:
        source=repo/name;dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,dest);r['sources'][name]=sha(source)
    r['known']=dict(phase=known(),spectral=spectral_known())
    fitted=load(a.fit/'report.json');assert fitted['result']=='source_VAR2_stable_pending_waveform_and_listening'
    assert sha(a.fit/'model.json')==fitted['model_sha256']
    root=a.workspace/'baselines'
    paths=dict(profile=root/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json',
      law=root/'idle_positive_power_v1/evidence/observe1/report.json',
      budget=root/'idle_post_budget_v1/evidence/observe1/report.json',
      source=root/'idle_closure_evidence_v1/evidence/observe1/source_train.npz')
    for key,path in paths.items():r['inputs'][key]=dict(path=str(path),sha256=sha(path))
    profile=load(paths['profile']);law=load(paths['law'])['observations'][0]['models']['expanded']
    allocation=load(paths['budget'])['allocation'];assert allocation['generative']
    with np.load(paths['source']) as data:source=data['phasors']
    model=synthesis_frame(spectral_fit(load(a.fit/'model.json'),source),source);save(a.out/'model.json',model)
    r.update(fit_report_sha256=sha(a.fit/'report.json'),model_sha256=sha(a.out/'model.json'),
      probabilities=allocation['probability'],law=law,methods=METHODS,
      original_three_frequencies_hz=np.asarray(profile['modal']['frequencies_hz'])[[1,2,4]].tolist(),
      generated_mean_carrier_frequencies_hz=(H*model['carrier_hz']).tolist())
    bands=[[20,80],[80,300],[300,1200],[1200,2200],[2200,4000],[4000,8000],[8000,14000],[14000,20000]]
    for seed,seconds in [(149921,180),(277139,24),(381611,24)]:
        audio,extra=render(profile,model,law,allocation['probability'],seed,seconds*48000)
        row=dict(seed=seed,seconds=seconds,files={},blocks=[],events=extra.pop('events'))
        path=a.out/f'motion_{seed}.npz';np.savez_compressed(path,**extra)
        row['motion_file']=path.name;row['motion_sha256']=sha(path)
        for name,y in audio.items():
            assert np.isfinite(y).all() and abs(y).max()<1.,(seed,name,'No peak normalization')
            path=a.out/f'{name}_{seed}.wav';sf.write(path,y,48000,subtype='FLOAT')
            actual,rate=sf.read(path,always_2d=True);assert rate==48000 and len(actual)==seconds*48000
            row['files'][name]=dict(file=path.name,sha256=sha(path),frames=len(actual),peak=float(abs(actual).max()),
              rms_LR=np.sqrt(np.mean(actual**2,axis=0)).tolist())
            if name in METHODS:
                for start in range(0,len(actual),144000):
                    part=actual[start:start+144000]
                    hz,psd=signal.welch(part[:,0],48000,nperseg=8192,noverlap=4096)
                    row['blocks'].append(dict(method=name,start_seconds=start/48000,
                      peak=float(abs(part).max()),rms_LR=np.sqrt(np.mean(part**2,axis=0)).tolist(),
                      bandpower=[float(psd[(hz>=lo)&(hz<hi)].sum()*48000/8192) for lo,hi in bands]))
        r['renders'].append(row)
        print(dict(stage='rendered',seed=seed,seconds=seconds,peak=max(x['peak'] for x in row['files'].values())),flush=True)
    for part in ['training','check']:
        path=root/f'idle_excitation_moments_v1/evidence/observe1/{part}.npz'
        with np.load(path) as data:x=data['audio']
        out=a.out/f'reference_{part}.wav';sf.write(out,x,48000,subtype='FLOAT')
        r['inputs']['reference_'+part]=dict(path=str(path),sha256=sha(path),out_sha256=sha(out))
    r.update(result='new_stationary_idle_phase_audio_pending_independent_audit',bands_hz=bands,
      sample_rate=48000,all_seeds_and_blocks_retained=True,source_PCM_used_for_synthesis=False,
      runtime_changed=False,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],renders=len(r['renders'])),flush=True)
