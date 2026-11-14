"""Post-spectral compatibility diagnostic: same OU model, source-shaped Gaussian carrier, no refit."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha
from accel_upper_am_v1.model import predict

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',input_sha256=sha(a.input/'report.json'),sources={},cases=[])
try:
    for name in ['tools/observe_accel_upper_carrier_energy_v1.py','tools/accel_upper_am_v1/model.py',
                 'tools/accel_upper_forward_v1/kernel.py','research/accel_upper_carrier_v1_energy_followup.json']:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    run=load(a.input/'report.json');assert run['result']=='all12_source_carriers_and_gain_budgets_complete'
    parent=a.workspace/'baselines/accel_upper_am_v1';assert sha(parent/'manifest.json')==run['parents']['gain']['manifest_sha256']
    for row in run['observations']:
        path=a.input/row['file'];assert sha(path)==row['sha256']
        parent_path=parent/row['gain_parent_file'];assert sha(parent_path)==run['parents']['gain']['files'][row['gain_parent_file']]
        with np.load(path) as f,np.load(parent_path) as old:
            lags=f['lags'];Rc=f['covariance'];native=old['native_lags'];indices=native-int(lags[0]);power=np.diag(Rc[-int(lags[0])]);assert min(power)>0
            squared=Rc[indices]**2/np.outer(power,power)
            operator=dict(W=old['W'],native_lags=native,carrier_squared_normalized=squared,sample_rate=48000)
            new=predict(operator,old['parameters']);target=old['target'];before=old['prediction']
            file=a.out/(row['segment']+'_'+row['branch']+'.npz')
            np.savez_compressed(file,target=target,previous=before,prediction=new,parameters=old['parameters'],native_lags=native,
                carrier_squared=squared,W=old['W'])
            old_cost=float(np.sum((before-target)**2)/2);new_cost=float(np.sum((new-target)**2)/2)
            r['cases'].append(dict(segment=row['segment'],branch=row['branch'],file=file.name,sha256=sha(file),
                source_file=row['file'],gain_parent_file=row['gain_parent_file'],previous_cost=old_cost,new_cost=new_cost,
                previous_max_error=float(abs(before-target).max()),new_max_error=float(abs(new-target).max()),
                model_parameters_changed=False,gain_fit_available=row['gain_fit_available']))
        save(a.out/'report.json',r)
        print(dict(segment=row['segment'],branch=row['branch'],old_cost=old_cost,new_cost=new_cost),flush=True)
    assert len(r['cases'])==12;r.update(result='all12_fixed_gain_carrier_compatibility_diagnosed',refitted=False,new_listening_audio=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
