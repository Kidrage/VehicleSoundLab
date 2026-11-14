"""Exact second Gaussian chaos of all frozen native conditional energy observers."""
import argparse,os,shutil,sys,time
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:parser.add_argument('--'+key,type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(args.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha
from accel_observer_second_v1.model import compile_locals,combine
from accel_observer_second_v1.known import known

args.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},parent_files={},observations=[])
try:
    for name in ['tools/observe_accel_observer_second_v1.py','tools/accel_observer_second_v1/model.py','tools/accel_observer_second_v1/known.py',
        'tools/accel_observer_projection_v1/model.py','tools/accel_observer_bound_v1/known.py','tools/accel_observer_bound_v1/model.py','tools/research_archive_v1.py','research/accel_observer_second_v1_plan.json']:
        dest=args.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    r['known'],known_arrays=known();np.savez_compressed(args.out/'known.npz',**known_arrays);r['known_sha256']=sha(args.out/'known.npz')
    save(args.out/'report.json',r);print(dict(known_max=r['known']['maximum_dense_or_four_time_error']),flush=True)
    parent=args.workspace/'baselines/accel_observer_projection_v1';r['parent_manifest_sha256']=sha(parent/'manifest.json');table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    def read(name):
        path=parent/name;assert sha(path)==table[name];r['parent_files'][name]=table[name];return path
    previous=load(read('evidence/observe1/report.json'));assert load(read('evidence/audit1/report.json'))['result']=='passed'
    for row in previous['observations']:
        old_name='evidence/observe1/'+row['file'];values=[];local_files=[]
        with np.load(read(old_name)) as old:
            for i in range(4):
                start=time.perf_counter();gamma=float(old['gamma'][i]);tau=float(old['tau']);tile=old['tile']
                locals_=compile_locals(gamma,tau,old['carrier_R'][:,i],tile);value,group=combine(gamma,tau,tile,locals_);values.append(value)
                for m,local in locals_.items():
                    file=args.out/f'{row["segment"]}_{row["branch"]}_c{i}_m{m}.npz';np.savez_compressed(file,**local)
                    local_files.append(dict(coordinate=i,windows=m,file=file.name,sha256=sha(file),native_length=m*480))
                group_file=args.out/f'{row["segment"]}_{row["branch"]}_c{i}_groups.npz';np.savez_compressed(group_file,**group)
                local_files.append(dict(coordinate=i,groups=True,file=group_file.name,sha256=sha(group_file)))
                print(dict(segment=row['segment'],branch=row['branch'],coordinate=i,seconds=time.perf_counter()-start,second=value['second_variance_pooled'],upper=value['variance_upper_pooled']),flush=True)
            arrays={key:np.array([value[key] for value in values]) for key in values[0]}
            np.testing.assert_allclose(arrays['expected'],old['expected'],rtol=1e-10,atol=1e-12)
            np.testing.assert_allclose(arrays['first_variance_pooled'],old['first_variance_pooled'],rtol=1e-9,atol=1e-15)
            np.testing.assert_allclose(arrays['absolute_ou_quadratic'],old['absolute_ou_quadratic_run'],rtol=1e-9,atol=1e-15)
            for key in ['actual','conditional','source_target','gamma','tau','tile','carrier_R','path_difference','carrier_difference','total_difference']:arrays[key]=old[key]
            arrays.update(prior_path_upper=old['combined_path_upper'],prior_total_upper=old['combined_total_upper'],prior_carrier_upper=old['prior_carrier_upper'])
            arrays['combined_path_upper']=np.minimum(arrays['variance_upper_pooled'],arrays['prior_path_upper']);arrays['combined_total_upper']=arrays['combined_path_upper']+arrays['prior_carrier_upper']
            assert np.all(arrays['second_variance_pooled']>=0) and np.all(arrays['variance_lower_pooled']<=arrays['combined_path_upper']+1e-12)
            for name in ['path','total']:
                delta=arrays[name+'_difference'];bound=arrays['combined_'+name+'_upper'];arrays[name+'_tail_upper']=np.array([1. if d==0 else min(1.,v/d**2) for v,d in zip(bound,delta)])
            file=args.out/(row['segment']+'_'+row['branch']+'.npz');np.savez_compressed(file,**arrays)
        r['observations'].append(dict(segment=row['segment'],branch=row['branch'],fit_available=row['fit_available'],old_parent_file=old_name,
            file=file.name,sha256=sha(file),local_files=local_files,first=arrays['first_variance_pooled'].tolist(),second=arrays['second_variance_pooled'].tolist(),
            lower=arrays['variance_lower_pooled'].tolist(),upper=arrays['combined_path_upper'].tolist(),total_upper=arrays['combined_total_upper'].tolist()))
        save(args.out/'report.json',r)
    assert len(r['observations'])==12
    r.update(result='all12_full_native_second_chaos_and_cubic_remainders_complete',cases=12,coordinates=48,not_full_variance_or_CI=True,new_audio=False,new_seeds=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(args.out/'report.json',r)
print(dict(result=r['result']),flush=True)
