"""Fit all frozen energy targets with the source-shaped Gaussian matrix carrier, after known qualification."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha
from accel_upper_coloured_v1.model import compile_matrix_observer
from accel_upper_coloured_v1.known import known
from accel_upper_am_v1.model import predict,fit,unpack,INITIAL,LOWER,UPPER
from accel_upper_carrier_v1.spectral import apply_gain,refilter,density,summaries

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},parent_files={},observations=[])
try:
    for name in ['tools/fit_accel_upper_coloured_v1.py','tools/accel_upper_coloured_v1/model.py','tools/accel_upper_coloured_v1/known.py',
                 'tools/accel_upper_am_v1/model.py','tools/accel_upper_forward_v1/kernel.py','tools/accel_upper_carrier_v1/spectral.py',
                 'tools/research_archive_v1.py','research/accel_upper_coloured_v1_plan.json']:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    r['known'],arrays=known();np.savez_compressed(a.out/'known.npz',**arrays);r['known_sha256']=sha(a.out/'known.npz');save(a.out/'report.json',r)
    print(dict(known_recovery=r['known']['known_recovery_error'],condition=r['known']['known_fit']['condition']),flush=True)
    parent=a.workspace/'baselines/accel_upper_carrier_v1';r['parent_manifest_sha256']=sha(parent/'manifest.json');table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    def read(name):
        path=parent/name;assert sha(path)==table[name];r['parent_files'][name]=table[name];return path
    previous=load(read('evidence/observe1/report.json'));compatibility=load(read('evidence/energy1/report.json'));assert load(read('evidence/audit2/report.json'))['result']=='passed'
    old_fits=load(read('inputs/parents/gain/evidence/fit1/report.json'))
    for before,compatible,old_record in zip(previous['observations'],compatibility['cases'],old_fits['observations']):
        assert before['segment']==compatible['segment']==old_record['segment'] and before['branch']==compatible['branch']==old_record['branch']
        carrier_name='evidence/observe1/'+before['file'];gain_name='inputs/parents/gain/'+before['gain_parent_file']
        with np.load(read(carrier_name)) as f,np.load(read(gain_name)) as old:
            impulse=f['impulse'];tile=old['tile'];target=old['target'];operator=compile_matrix_observer(impulse,tile)
            assert abs(operator['W']-old['W']).max()<1e-12 and np.array_equal(operator['native_lags'],old['native_lags'])
            old_parameters=old['parameters'];fixed=predict(operator,old_parameters)
            result,prediction,J=fit(operator,target);L,Gamma,tau=unpack(result['parameters'])
            Rg=apply_gain(f['lags'],f['covariance'],Gamma,tau);lf,Rfg=refilter(f['lags'],Rg,f['q'])
            spectra=dict(Welch_gain=density(f['lags'],Rg,12000,12000),Welch_refilter_gain=density(lf,Rfg,12000,12000))
            file=a.out/(before['segment']+'_'+before['branch']+'.npz')
            np.savez_compressed(file,impulse=impulse,tile=tile,target=target,prediction=prediction,J=J,parameters=np.array(result['parameters']),
                L=L,Gamma=Gamma,W=operator['W'],native_lags=operator['native_lags'],carrier_squared=operator['carrier_squared_normalized'],
                window_to_within=operator['window_to_within'],counts=operator['counts'],initial=INITIAL,lower=LOWER,upper=UPPER,
                old_parameters=old_parameters,white_prediction=old['prediction'],fixed_prediction=fixed,gain_covariance=Rg,
                refilter_lags=lf,refilter_gain_covariance=Rfg,**spectra)
        r['observations'].append(dict(segment=before['segment'],branch=before['branch'],carrier_parent_file=carrier_name,gain_parent_file=gain_name,
            file=file.name,sha256=sha(file),L=L.tolist(),Gamma=Gamma.tolist(),tau_seconds=tau,fit=result,
            old_white_cost=old_record['fit']['cost'],old_fit_available=old_record['fit']['available'],fixed_coloured_cost=compatible['new_cost'],
            maximum_error=float(abs(prediction-target).max()),summaries={key:summaries(value,12000) for key,value in spectra.items()}))
        save(a.out/'report.json',r);print(dict(segment=before['segment'],branch=before['branch'],available=result['available'],nfev=result['nfev'],
            tau=tau,cost=result['cost'],fixed=compatible['new_cost'],bound=result['bound_mask']),flush=True)
    assert len(r['observations'])==12;r.update(result='all12_source_carrier_joint_gain_fits_terminal',new_listening_audio=False,new_profile=False,runtime_changed=False,
        carrier_frozen_not_refitted=True,post_gain_observer_before_refilter=True,numeric_availability_not_timbre_acceptance=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result']),flush=True)
