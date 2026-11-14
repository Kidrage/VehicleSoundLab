"""Qualify phase-aware idle magnitudes before proposing any fresh AM generator."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha
from idle_phase_amplitude_v1.known import run
from idle_phase_amplitude_v1.observe import observe,statistics

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},inputs={},observations=[])
def track(path):r['inputs'][str(path)]=sha(path);return path
try:
    names=['tools/observe_idle_phase_amplitude_v1.py','tools/idle_phase_amplitude_v1/observe.py',
        'tools/idle_phase_amplitude_v1/known.py','tools/idle_conditioned_detail_v1/features.py',
        'research/idle_phase_amplitude_v1_plan.json','tools/research_archive_v1.py']
    for name in names:
        path=a.out/'exact_sources'/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,path)
        r['sources'][name]=sha(repo/name)
    r['known'],arrays=run();np.savez_compressed(a.out/'known.npz',**arrays)
    print(dict(stage='known',result=r['known']),flush=True)
    parent=a.workspace/'baselines';origin=parent/'idle_conditioned_detail_v1/evidence/observe1'
    profile=load(track(parent/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json'))
    for seed in [None,149921,277139,381611]:
        for part in ['train','check']:
            with np.load(track(origin/(part+'.npz'))) as f:audio=f['audio'];z=f['phasors']
            if seed is not None:
                fft=np.fft.rfft(audio,axis=0);phase=np.random.default_rng(seed).uniform(-np.pi,np.pi,len(fft));phase[0]=phase[-1]=0
                audio=np.fft.irfft(fft*np.exp(1j*phase[:,None]),n=len(audio),axis=0)
                with np.load(track(origin/f'{part}_phase_{seed}.npz')) as f:z=f['phasors']
            label=('source' if seed is None else 'phase_'+str(seed))+'_'+part
            fixed=observe(audio,profile['modal']['frequencies_hz']);aware=observe(audio,profile['modal']['frequencies_hz'],z)
            fixed_stats,fixed_log=statistics(fixed['coefficients']);aware_stats,aware_log=statistics(aware['coefficients'])
            path=a.out/(label+'.npz');np.savez_compressed(path,starts=aware['starts'],fixed=fixed['coefficients'],
                aware=aware['coefficients'],fixed_log=fixed_log,aware_log=aware_log,
                fixed_condition=fixed['condition'],aware_condition=aware['condition'])
            row=dict(label=label,seed=seed,part=part,file=path.name,sha256=sha(path),fixed=fixed_stats,aware=aware_stats,
                     max_condition=float(aware['condition'].max()))
            r['observations'].append(row);save(a.out/'report.json',r)
            print(dict(stage='source',label=label,aware_std=aware_stats['raw_log_std'],fixed_std=fixed_stats['raw_log_std'],
                       aware_rho=aware_stats['trace_200ms_correlation']),flush=True)
    r.update(result='phase_aware_idle_amplitude_observed',check_used_for_fit=False,new_audio_generated=False,
             recorded_trajectory_exported_to_runtime=False,runtime_changed=False,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
