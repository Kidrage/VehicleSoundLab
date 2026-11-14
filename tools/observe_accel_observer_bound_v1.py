"""Actual finite energy-observer bounds on all frozen models; no new generated stream."""
import argparse,os,shutil,sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:parser.add_argument('--'+key,type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(args.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha
from accel_observer_bound_v1.model import bounds,tail
from accel_observer_bound_v1.known import known

args.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},parent_files={},observations=[])
try:
    for name in ['tools/observe_accel_observer_bound_v1.py','tools/accel_observer_bound_v1/model.py','tools/accel_observer_bound_v1/known.py',
                 'tools/research_archive_v1.py','research/accel_observer_bound_v1_plan.json']:
        dest=args.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    r['known'],arrays=known();np.savez_compressed(args.out/'known.npz',**arrays);r['known_sha256']=sha(args.out/'known.npz')
    save(args.out/'report.json',r);print(dict(known_fixtures=len(r['known']['fixtures']),maximum_mean_error=r['known']['maximum_mean_error']),flush=True)
    parent=args.workspace/'baselines/accel_upper_conditional_v1';r['parent_manifest_sha256']=sha(parent/'manifest.json')
    table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    def read(name):
        path=parent/name;assert sha(path)==table[name];r['parent_files'][name]=table[name];return path
    previous=load(read('evidence/observe1/report.json'));assert load(read('evidence/audit1/report.json'))['result']=='passed'
    for row in previous['observations']:
        model_name='inputs/parent/'+row['model_parent_file'];carrier_name='inputs/parent/'+row['carrier_parent_file'];old_name='evidence/observe1/'+row['file']
        with np.load(read(model_name)) as model,np.load(read(carrier_name)) as c,np.load(read(old_name)) as old:
            G=model['L']@model['L'].T;tau=float(model['parameters'][-1]);R=c['covariance'][len(c['impulse'])-1:][:,[0,1,2,3],[0,1,2,3]]
            values=[bounds(G[i,i],tau,R[:,i],model['tile']) for i in range(4)];expected=np.array([v['expected'] for v in values])
            np.testing.assert_allclose(expected,old['expected'],rtol=1e-10,atol=1e-12)
            actual=old['actual'];conditional=old['conditional'];deltas={'path':(conditional-expected).mean(axis=(0,1)),
                'carrier':(actual-conditional).mean(axis=(0,1)),'total':(actual-expected).mean(axis=(0,1))}
            file=args.out/(row['segment']+'_'+row['branch']+'.npz')
            arrays={key:np.array([v[key] for v in values]) for key in values[0]}
            arrays.update(actual=actual,conditional=conditional,source_target=old['source_target'],gamma=np.diag(G),tau=tau,tile=model['tile'],carrier_R=R)
            for name,delta in deltas.items():
                arrays[name+'_difference']=delta;arrays[name+'_marginal_Chebyshev_upper']=np.array([tail(values[i][name+'_variance_bound_pooled'],delta[i]) for i in range(4)])
            np.savez_compressed(file,**arrays)
        r['observations'].append(dict(segment=row['segment'],branch=row['branch'],fit_available=row['fit_available'],model_parent_file=model_name,
            carrier_parent_file=carrier_name,old_parent_file=old_name,file=file.name,sha256=sha(file),bounds=values,
            marginal_total_tail_upper=arrays['total_marginal_Chebyshev_upper'].tolist()))
        save(args.out/'report.json',r);print(dict(segment=row['segment'],branch=row['branch'],total_variance_bound=arrays['total_variance_bound_pooled'].tolist(),
            tail_upper=arrays['total_marginal_Chebyshev_upper'].tolist()),flush=True)
    assert len(r['observations'])==12
    r.update(result='all12_actual_energy_observer_variance_upper_bounds_complete',cases=12,coordinates=48,
        not_exact_variances_or_confidence_intervals=True,zero_lag_diagonal_pre_refilter_only=True,new_audio=False,new_seeds=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(args.out/'report.json',r)
print(dict(result=r['result']),flush=True)
