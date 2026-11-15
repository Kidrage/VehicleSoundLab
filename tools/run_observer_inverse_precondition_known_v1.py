"""Dense independent verification of an invertible right map, no material."""
import argparse,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','known','known-audit','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_forward_v1.polyphase import PolyphaseObserver
    from observer_inverse_v1.precondition import RightMap,infer_preconditioned
    from observer_inverse_v1.fit import RegularizedObserver,real_vector
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',cases=[],sources={},material_read=False)
    names=('tools/run_observer_inverse_precondition_known_v1.py','tools/observer_inverse_v1/precondition.py')
    for name in names:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
    try:
        old=load(a.known/'report.json');audit=load(a.known_audit/'report.json')
        assert audit['result']=='independent_observer_inverse_known_passed' and audit['producer_sha256']==sha(a.known/'report.json')
        for name,digest in old['sources'].items():assert sha(repo/name)==digest
        with np.load(a.known/'dense_system.npz') as z:c={k:z[k] for k in z.files}
        assert sha(a.known/'dense_system.npz')==old['dense_sha256']
        op=PolyphaseObserver(int(c['frames']),c['positions'],c['orders'],c['orders']);system=RegularizedObserver(op,c['scale']);right=RightMap(system)
        P=np.kron(right.time,np.eye(len(op.orders)*op.channels))
        dr=np.broadcast_to(right.real_scale,op.shape).ravel();di=np.broadcast_to(right.imag_scale,op.shape).ravel()
        dense_right=linalg.block_diag(P*dr[None,:],P*di[None,:]);dense=c['matrix']@dense_right
        norm_error=float(abs((dense*dense).sum(axis=0)-1).max());assert norm_error<2e-9,norm_error
        rng=np.random.default_rng(51829);x=rng.normal(size=system.nsize);y=rng.normal(size=system.nsize)
        assert abs(right.apply(x)-dense_right@x).max()<2e-10
        assert abs(right.transpose(y)-dense_right.T@y).max()<2e-10
        assert abs(np.dot(y,right.apply(x))-np.dot(right.transpose(y),x))<2e-9
        np.savez_compressed(a.out/'right_map.npz',time=right.time,real_scale=right.real_scale,imag_scale=right.imag_scale,dense_right=dense_right,normal_column_norms=(dense*dense).sum(axis=0))
        for desc in old['solves']:
            with np.load(a.known/desc['file']) as z:target=z['target'];truth=z['dense_solution'];rhs=z['rhs']
            nodes,info,_=infer_preconditioned(op,target,c['scale']);solution=real_vector(nodes/c['scale'][None])
            error=float(np.linalg.norm(solution-truth)/np.linalg.norm(truth));assert info['converged'] and error<2e-7,(desc['name'],info,error)
            objective=float(np.linalg.norm(c['matrix']@solution-rhs)**2);assert abs(objective-info['objective'])<2e-9*max(1,objective)
            path=a.out/(desc['name']+'.npz');np.savez_compressed(path,nodes=nodes,solution=solution,target=target)
            r['cases'].append(dict(name=desc['name'],file=path.name,sha256=sha(path),relative_dense_solution_error=error,**info))
        r.update(result='observer_inverse_precondition_known_ready',all3_same_objective_solutions_verified=True,
            column_norm_error=norm_error,right_map_sha256=sha(a.out/'right_map.npz'),parent_known_sha256=sha(a.known/'report.json'),
            parent_audit_sha256=sha(a.known_audit/'report.json'),parent_dense_sha256=sha(a.known/'dense_system.npz'))
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
