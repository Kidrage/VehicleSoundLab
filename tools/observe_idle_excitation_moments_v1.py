"""Training-only idle excitation moment compilation, all controls retained."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from research_archive_v1 import load,save,sha
from drive_evidence_v1.sources import read
from idle_modal_v1.modal import render
from idle_excitation_moments_v1.moments import observe,compile_model,known_controls

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},observations=[])
try:
    plan_path=repo/'research/idle_excitation_moments_v1_plan.json';plan=load(plan_path)
    for path in [Path(__file__),plan_path,repo/'tools/research_archive_v1.py',
                 repo/'tools/drive_evidence_v1/sources.py',repo/'tools/idle_modal_v1/modal.py',
                 *sorted((repo/'tools/idle_excitation_moments_v1').glob('*.py'))]:
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][name.as_posix()]=sha(path)
    r['known']=known_controls()
    audio,provenance=read(a.workspace,'F2_tailpipe','recording_power')
    profile_path=a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json'
    profile=load(profile_path);sos=np.array([signal.butter(4,band,btype='bandpass',fs=48000,output='sos') for band in plan['bands_hz']])
    train=audio[:144000];stats,filtered=observe(train,sos,plan['trim_frames'])
    np.savez_compressed(a.out/'training.npz',audio=train,filtered=filtered,sos=sos)
    r['train']=stats;r['phase_controls']=[]
    z=np.fft.rfft(train,axis=0)
    for seed in plan['seeds']:
        phase=np.random.default_rng(seed).uniform(-np.pi,np.pi,len(z));phase[0]=phase[-1]=0
        shifted=np.fft.irfft(z*np.exp(1j*phase[:,None]),n=len(train),axis=0)
        control,bands=observe(shifted,sos,plan['trim_frames'])
        np.savez_compressed(a.out/f'phase_{seed}.npz',audio=shifted,filtered=bands)
        r['phase_controls'].append(dict(seed=seed,statistics=control))
    if not np.all(np.array(stats['excess'])>np.array([x['statistics']['excess'] for x in r['phase_controls']])):
        raise ValueError('Not every source band exceeds every same-PSD phase control')
    main=render(profile['modal'],144000,48000)
    model,evidence,impulses=compile_model(profile,main,stats,sos,plan)
    save(a.out/'model.json',model);save(a.out/'moment_budget.json',evidence)
    np.savez_compressed(a.out/'effective_impulses.npz',impulses=impulses,main=main)
    # Check is observed only after immutable model and budget are saved.
    check,filtered=observe(audio[144000:],sos,plan['trim_frames'])
    np.savez_compressed(a.out/'check.npz',audio=audio[144000:],filtered=filtered,sos=sos)
    r.update(result='moment_candidate_compiled',plan=plan,profile_path=str(profile_path),
             profile_sha256=sha(profile_path),provenance=provenance,check=check,
             check_used_for_fit=False,model_sha256=sha(a.out/'model.json'),runtime_changed=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],train_excess=stats['excess'],check_excess=check['excess'],model=model,budget=evidence['relative_residual']),flush=True)
