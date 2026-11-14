"""Qualify raw-native complex modulation, then fit approved F2 TRAIN only."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha
from idle_complex75_v1.extract import extract
from idle_complex75_v1.model import fit,table
from idle_complex75_v1.known import run
a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},inputs={},known={},portions=[])


def track(path):r['inputs'][str(path)]=sha(path);return path
def checkpoint():save(a.out/'report.json',r)


try:
    names=['tools/fit_idle_complex75_v1.py','tools/idle_complex75_v1/extract.py','tools/idle_complex75_v1/model.py',
        'tools/idle_complex75_v1/known.py','tools/idle_short_budget_v1/spectral.py','tools/idle_window_transfer_v1/observe.py',
        'tools/research_archive_v1.py','research/idle_complex75_v1_plan.json']
    for name in names:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    r['known'],arrays=run();np.savez_compressed(a.out/'known.npz',**arrays);checkpoint();print(dict(stage='known_pass',controls=r['known']),flush=True)
    root=a.workspace/'baselines';profile=load(track(root/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json'));freq=profile['modal']['frequencies_hz']
    origin=root/'idle_conditioned_detail_v1/evidence/observe1'
    for part in ['train','check']:
        with np.load(track(origin/(part+'.npz'))) as f:audio=f['audio'][:,0];z=f['phasors']
        result=extract(audio,freq,z);x=result['latent'];reference=result.pop('reference')
        file=a.out/(part+'.npz');np.savez_compressed(file,reference=reference,**result)
        if part=='train':
            model=fit(x);compiled=table(model);save(a.out/'model.json',model)
            np.savez_compressed(a.out/'interpolation.npz',**compiled);r['model_sha256']=sha(a.out/'model.json')
        r['portions'].append(dict(part=part,file=file.name,sha256=sha(file),reference=[reference.real,reference.imag],
            covariance=(x.T@x/len(x)).tolist(),raw_mean=result['mean'].tolist(),
            minimum_relative_amplitude=float(abs(result['relative_envelope']).min()),
            maximum_relative_phase=float(abs(np.angle(result['relative_envelope'])).max())))
        checkpoint();print(dict(part=part,covariance=r['portions'][-1]['covariance']),flush=True)
    r.update(result='source_native_complex75_fitted_pending_audit',fit_source='F2_train_6_9_only',CHECK_used_for_fit=False,
        PCM_or_recorded_trajectory_in_model=False,new_audio=False,new_C=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:checkpoint()
print(dict(result=r['result'],portions=r['portions']),flush=True)
