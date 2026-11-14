"""Retain signed native group cancellations in all actual conditional-observer first projections."""
import argparse,os,shutil,sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:parser.add_argument('--'+key,type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(args.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha
from accel_observer_projection_v1.model import coefficients,project
from accel_observer_projection_v1.known import known

args.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},parent_files={},observations=[])
try:
    for name in ['tools/observe_accel_observer_projection_v1.py','tools/accel_observer_projection_v1/model.py','tools/accel_observer_projection_v1/known.py',
                 'tools/accel_observer_bound_v1/known.py','tools/accel_observer_bound_v1/model.py','tools/research_archive_v1.py','research/accel_observer_projection_v1_plan.json']:
        dest=args.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    r['known'],known_arrays=known();np.savez_compressed(args.out/'known.npz',**known_arrays);r['known_sha256']=sha(args.out/'known.npz')
    save(args.out/'report.json',r);print(dict(known=r['known']),flush=True)
    parent=args.workspace/'baselines/accel_observer_bound_v1';r['parent_manifest_sha256']=sha(parent/'manifest.json')
    table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    def read(name):
        path=parent/name;assert sha(path)==table[name];r['parent_files'][name]=table[name];return path
    previous=load(read('evidence/observe1/report.json'));assert load(read('evidence/audit1/report.json'))['result']=='passed'
    for row in previous['observations']:
        old_name='evidence/observe1/'+row['file'];values=[];signed=[];absolute=[]
        with np.load(read(old_name)) as old:
            for i in range(4):
                t,a=coefficients(float(old['gamma'][i]),float(old['tau']),old['carrier_R'][:,i],old['tile'])
                signed.append(t);absolute.append(a);values.append(project(float(old['gamma'][i]),float(old['tau']),t,a))
            arrays={key:np.array([v[key] for v in values]) for key in values[0]}
            np.testing.assert_allclose(arrays['expected'],old['expected'],rtol=1e-10,atol=1e-12)
            for key in ['actual','conditional','source_target','gamma','tau','tile','carrier_R','path_difference','carrier_difference','total_difference']:arrays[key]=old[key]
            arrays.update(signed_coefficient=np.column_stack(signed),absolute_coefficient=np.column_stack(absolute),
                prior_path_upper=old['path_variance_bound_pooled'],prior_carrier_upper=old['carrier_variance_bound_pooled'],prior_total_upper=old['total_variance_bound_pooled'])
            arrays['combined_path_upper']=np.minimum(arrays['variance_upper_pooled'],arrays['prior_path_upper'])
            arrays['combined_total_upper']=arrays['combined_path_upper']+arrays['prior_carrier_upper']
            assert np.all(arrays['first_variance_pooled']<=arrays['combined_path_upper']+1e-12)
            for name in ['path','total']:
                delta=arrays[name+'_difference'];bound=arrays['combined_'+name+'_upper']
                arrays[name+'_marginal_tail_upper']=np.array([1. if d==0 else min(1.,b/d**2) for b,d in zip(bound,delta)])
            file=args.out/(row['segment']+'_'+row['branch']+'.npz');np.savez_compressed(file,**arrays)
        r['observations'].append(dict(segment=row['segment'],branch=row['branch'],fit_available=row['fit_available'],old_parent_file=old_name,file=file.name,sha256=sha(file),
            first_variance_pooled=arrays['first_variance_pooled'].tolist(),projection_upper_pooled=arrays['variance_upper_pooled'].tolist(),combined_path_upper=arrays['combined_path_upper'].tolist(),
            combined_total_upper=arrays['combined_total_upper'].tolist(),path_tail_upper=arrays['path_marginal_tail_upper'].tolist(),total_tail_upper=arrays['total_marginal_tail_upper'].tolist()))
        save(args.out/'report.json',r);print(dict(segment=row['segment'],branch=row['branch'],lower=arrays['first_variance_pooled'].tolist(),
            upper=arrays['combined_path_upper'].tolist(),path_tail_upper=arrays['path_marginal_tail_upper'].tolist()),flush=True)
    assert len(r['observations'])==12
    r.update(result='all12_signed_native_observer_projections_and_remainders_complete',cases=12,coordinates=48,
        first_projection_not_full_variance=True,variance_brackets_not_CI=True,new_audio=False,new_seeds=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(args.out/'report.json',r)
print(dict(result=r['result']),flush=True)
