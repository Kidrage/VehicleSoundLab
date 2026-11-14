"""Run the native shared-iid forward kernel against all original F3 energy lag observations."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from scipy import signal
from research_archive_v1 import load,save,sha
from accel_upper_forward_v1.known import known
from accel_upper_forward_v1.kernel import native_basis,rectangular_basis,within_basis

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},parent_files={},observations=[])
try:
    for name in ['tools/observe_accel_upper_forward_v1.py','tools/accel_upper_forward_v1/kernel.py','tools/accel_upper_forward_v1/known.py',
                 'tools/research_archive_v1.py','research/accel_upper_forward_v1_plan.json']:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    r['known'],arrays=known();np.savez_compressed(a.out/'known.npz',**arrays);save(a.out/'report.json',r);print(dict(known=r['known']),flush=True)
    parent=a.workspace/'baselines/accel_upper_joint_v1';r['parent_manifest_sha256']=sha(parent/'manifest.json')
    table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    def read(name):
        path=parent/name;assert sha(path)==table[name];r['parent_files'][name]=table[name];return path
    previous=load(read('evidence/observe1/report.json'));assert load(read('evidence/audit1/report.json'))['result']=='passed'
    for row in previous['observations']:
        with np.load(read('evidence/observe1/'+row['file'])) as old:sos=old['sos'];tile=old['tile'];power=old['power']
        unit=np.zeros(8192);unit[0]=1;impulse=np.column_stack([signal.sosfilt(s,unit) for s in sos for ch in range(2)])
        tail=np.sum(impulse[-1024:]**2,axis=0)/np.sum(impulse**2,axis=0);assert np.max(tail)<1e-24
        native=native_basis(impulse);maxlag=max(int(sum(tile==tag))-1 for tag in np.unique(tile))
        window=rectangular_basis(native,480,maxlag);lags=np.arange(-5,6);within=within_basis(window,tile,lags)
        observed=np.array(row['energy']['normalized_lagged']);gaussian=within['normalized_gaussian'];fourth=within['normalized_fourth']
        assert np.all(fourth[5]>0)
        coefficient=(observed[5]-gaussian[5])/fourth[5];feasible=coefficient>=0
        prediction=gaussian+coefficient[None,:,:]*fourth;closure=float(abs(prediction[5]-observed[5]).max());assert closure<1e-12
        diagnostic_error=prediction-observed
        file=a.out/(row['segment']+'_'+row['branch']+'.npz')
        np.savez_compressed(file,sos=sos,impulse=impulse,tail_fraction=tail,tile=tile,observed=observed,
            lags=lags,counts=within['counts'],power=native['power'],window_lags=window['lags'],
            window_gaussian=window['gaussian'],window_fourth=window['fourth'],gaussian=gaussian,fourth=fourth,
            coefficient=coefficient,feasible=feasible,prediction=prediction)
        pairs=[]
        for i in range(4):
            for j in range(4):
                pairs.append(dict(indices=[i,j],kappa=float(coefficient[i,j]),Bernoulli_Gaussian_available=bool(feasible[i,j]),
                    observed_all11=observed[:,i,j].tolist(),prediction_all11=prediction[:,i,j].tolist(),
                    gaussian_all11=gaussian[:,i,j].tolist(),fourth_all11=fourth[:,i,j].tolist(),
                    max_other_lag_error=float(abs(diagnostic_error[np.arange(11)!=5,i,j]).max()),
                    implied_Bernoulli_probability=float(3/(coefficient[i,j]+3)) if feasible[i,j] else None))
        r['observations'].append(dict(segment=row['segment'],branch=row['branch'],parent_file='evidence/observe1/'+row['file'],
            file=file.name,sha256=sha(file),energy_windows=len(power),group_lengths=[int(sum(tile==tag)) for tag in np.unique(tile)],
            tail_fraction=tail.tolist(),zero_lag_matching_by_construction=closure,pairs=pairs))
        save(a.out/'report.json',r);print(dict(segment=row['segment'],branch=row['branch'],tail=float(max(tail)),pairs=len(pairs)),flush=True)
    assert len(r['observations'])==12
    r.update(result='all12_shared_iid_forward_probes_complete',new_audio=False,new_profile=False,runtime_changed=False,
             multichannel_fit=False,pairwise_zero_lag_matches_not_validation=True,source_PSD_fitted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result']),flush=True)
