"""Qualify the joint OU gain forward/inverse, then fit every frozen F3 target once."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha
from accel_upper_am_v1.known import known
from accel_upper_am_v1.model import compile_observer,predict,fit,unpack,INITIAL,LOWER,UPPER

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},parent_files={},observations=[])
try:
    for name in ['tools/fit_accel_upper_am_v1.py','tools/accel_upper_am_v1/model.py','tools/accel_upper_am_v1/known.py',
                 'tools/accel_upper_forward_v1/kernel.py','tools/research_archive_v1.py','research/accel_upper_am_v1_plan.json']:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    r['known'],arrays=known();np.savez_compressed(a.out/'known.npz',**arrays);r['known_arrays_sha256']=sha(a.out/'known.npz')
    save(a.out/'report.json',r);print(dict(known_recovery=r['known']['known_recovery_error'],condition=r['known']['known_fit']['condition']),flush=True)
    parent=a.workspace/'baselines/accel_upper_forward_v1';r['parent_manifest_sha256']=sha(parent/'manifest.json')
    table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    def read(name):
        path=parent/name;assert sha(path)==table[name];r['parent_files'][name]=table[name];return path
    previous=load(read('evidence/observe1/report.json'));assert load(read('evidence/audit1/report.json'))['result']=='passed'
    for before in previous['observations']:
        with np.load(read('evidence/observe1/'+before['file'])) as f:
            impulse=f['impulse'];tile=f['tile'];target=f['observed'];old_gaussian=f['gaussian']
        operator=compile_observer(impulse,tile)
        baseline=predict(operator,np.r_[np.zeros(10),.025]);baseline_error=float(abs(baseline-old_gaussian).max());assert baseline_error<1e-11
        result,prediction,J=fit(operator,target);L,Gamma,tau=unpack(result['parameters'])
        file=a.out/(before['segment']+'_'+before['branch']+'.npz')
        np.savez_compressed(file,impulse=impulse,tile=tile,target=target,prediction=prediction,J=J,parameters=np.array(result['parameters']),
            L=L,Gamma=Gamma,W=operator['W'],native_lags=operator['native_lags'],carrier_squared=operator['carrier_squared_normalized'],
            window_to_within=operator['window_to_within'],counts=operator['counts'],baseline=baseline,
            initial=INITIAL,lower=LOWER,upper=UPPER)
        r['observations'].append(dict(segment=before['segment'],branch=before['branch'],parent_file='evidence/observe1/'+before['file'],
            file=file.name,sha256=sha(file),baseline_error=baseline_error,L=L.tolist(),Gamma=Gamma.tolist(),tau_seconds=tau,fit=result,
            maximum_error=float(abs(prediction-target).max())))
        save(a.out/'report.json',r);print(dict(segment=before['segment'],branch=before['branch'],available=result['available'],nfev=result['nfev'],tau=tau,
            cost=result['cost'],bound=result['bound_mask']),flush=True)
    assert len(r['observations'])==12
    r.update(result='all12_joint_positive_gain_fits_terminal',new_listening_audio=False,new_profile=False,runtime_changed=False,
        source_PSD_fitted=False,numerical_available_not_timbre_acceptance=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result']),flush=True)
