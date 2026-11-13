"""Training-only conditional idle detail, with all controls and check outcomes kept."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha
from idle_conditioned_detail_v1.features import observe
from idle_conditioned_detail_v1.model import fit,assess
from idle_conditioned_detail_v1.checks import controls

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},observations=[],audio_exported=False)
try:
    plan_path=repo/'research/idle_conditioned_detail_v1_plan.json';plan=load(plan_path)
    for path in [Path(__file__),plan_path,repo/'tools/research_archive_v1.py',*sorted((repo/'tools/idle_conditioned_detail_v1').glob('*.py'))]:
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][name.as_posix()]=sha(path)
    save(a.out/'known_controls.json',controls())
    parent=a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe'
    profile=load(parent/'profile.json');frequencies=np.array(profile['modal']['frequencies_hz'])[plan['modal_indices']]
    paths={'train':parent/'training.wav','check':a.workspace/'baselines/idle_texture_v2/inputs/F2_holdout.wav'}
    features={};power={};phasors={}
    for name,path in paths.items():
        x,rate=sf.read(path,always_2d=True);assert rate==48000 and x.shape==(144000,2)
        features[name],power[name],phasors[name]=observe(x,frequencies,plan['detail_bands_hz'])
        np.savez_compressed(a.out/(name+'.npz'),audio=x,feature=features[name],power=power[name],phasors=phasors[name])
        r['observations'].append(dict(name=name,input_path=str(path),input_sha256=sha(path)))
    model=fit(features['train'],power['train']);save(a.out/'model.json',dict(model,modal_indices=plan['modal_indices'],
        frequencies_hz=frequencies.tolist(),recorded_timeline=False,common_engine_phase=False))
    r['model']=model;r['real']={name:assess(model,features[name],power[name]) for name in paths}
    # Coefficients now frozen. Every same-PSD control is measured without tuning.
    r['phase_controls']=[]
    for seed in [149921,277139,381611]:
        subset={}
        for name,path in paths.items():
            x=sf.read(path,always_2d=True)[0];fft=np.fft.rfft(x,axis=0)
            phase=np.random.default_rng(seed).uniform(-np.pi,np.pi,len(fft));phase[0]=phase[-1]=0
            shifted=np.fft.irfft(fft*np.exp(1j*phase[:,None]),n=len(x),axis=0)
            assert abs(abs(np.fft.rfft(shifted,axis=0))-abs(fft)).max()<1e-10
            f,e,z=observe(shifted,frequencies,plan['detail_bands_hz']);subset[name]=(f,e)
            np.savez_compressed(a.out/f'{name}_phase_{seed}.npz',feature=f,power=e,phasors=z)
        control_model=fit(*subset['train'])
        row=dict(seed=seed,model=control_model,train=assess(control_model,*subset['train']),check=assess(control_model,*subset['check']))
        r['phase_controls'].append(row)
    actual=np.array(r['real']['check']['relative_mse_improvement'])
    contrast=np.array([x['check']['relative_mse_improvement'] for x in r['phase_controls']])
    supported=(actual>0)&np.all(actual>contrast,axis=0)
    r.update(result='conditional_amplitude_observed',plan=plan,frequencies_hz=frequencies.tolist(),
        supported_bands=supported.tolist(),candidate_gate=bool(model['positive'] and supported.sum()>=3),
        check_used_for_fit=False,same_recording_check=True,physical_source_identified=False,
        engine_phase_qualification=False,runtime_changed=False,parent_profile_sha256=sha(parent/'profile.json'))
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print({key:r[key] for key in ['result','candidate_gate','supported_bands','real']},flush=True)
