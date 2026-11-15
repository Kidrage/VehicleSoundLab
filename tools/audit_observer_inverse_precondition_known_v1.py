"""Audit right-map invertibility and solutions using only verified dense data."""
import argparse,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','known','known-audit','study','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',cases=[],material_read=False)
    try:
        producer=load(a.study/'report.json');assert producer['result']=='observer_inverse_precondition_known_ready'
        old=load(a.known/'report.json');ka=load(a.known_audit/'report.json')
        assert ka['result']=='independent_observer_inverse_known_passed' and ka['producer_sha256']==sha(a.known/'report.json')==producer['parent_known_sha256']
        assert sha(a.known_audit/'report.json')==producer['parent_audit_sha256']
        assert sha(a.known/'dense_system.npz')==old['dense_sha256']==producer['parent_dense_sha256']
        for name,d in producer['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==d
        for name,d in old['sources'].items():assert sha(repo/name)==d
        assert sha(a.study/'right_map.npz')==producer['right_map_sha256']
        with np.load(a.known/'dense_system.npz') as z:matrix=z['matrix'];positions=z['positions'];orders=z['orders'];scale=z['scale']
        with np.load(a.study/'right_map.npz') as z:P=z['time'];dr=z['real_scale'];di=z['imag_scale'];S=z['dense_right']
        M,H,C=len(positions),len(orders),2;size=M*H*C
        assert np.linalg.svd(P,compute_uv=False).min()>0 and np.all(dr>0) and np.all(di>0)
        # Recover the independently verified time penalty from the augmented
        # matrix. This audits P^T K P without recomputing its Cholesky algorithm.
        reg=matrix[2*3*H*C:];Kfull=reg.T@reg;K=Kfull[:size,:size][::H*C,::H*C]
        whitening=float(abs(P.T@K@P-np.eye(M)).max());assert whitening<2e-9
        rebuilt=np.zeros_like(S)
        for j in range(2*size):
            vec=np.zeros(2*size);vec[j]=1;z=(vec[:size]+1j*vec[size:]).reshape(M,H,C);q=np.empty_like(z)
            for h in range(H):
                for c in range(C):q[:,h,c]=P@(dr[:,h,0]*z[:,h,c].real)+1j*(P@(di[:,h,0]*z[:,h,c].imag))
            rebuilt[:,j]=np.r_[q.real.ravel(),q.imag.ravel()]
        assert abs(rebuilt-S).max()<2e-10
        norms=np.sum((matrix@S)**2,axis=0);assert abs(norms-1).max()<2e-9
        for desc in producer['cases']:
            path=a.study/desc['file'];assert sha(path)==desc['sha256']
            olddesc=next(x for x in old['solves'] if x['name']==desc['name'])
            with np.load(a.known/olddesc['file']) as z:rhs=z['rhs']
            with np.load(path) as z:x=z['solution']
            truth=np.linalg.lstsq(matrix,rhs,rcond=None)[0];err=float(np.linalg.norm(x-truth)/np.linalg.norm(truth));assert err<2e-7
            residual=matrix@x-rhs;gradient=matrix.T@residual;ratio=float(np.linalg.norm(gradient)/np.linalg.norm(matrix.T@rhs))
            assert ratio<2e-7 and abs(ratio-desc['relative_stationarity'])<2e-10
            assert abs(float(residual@residual)-desc['objective'])<2e-9*max(1,desc['objective'])
            r['cases'].append(dict(name=desc['name'],relative_solution_error=err,relative_stationarity=ratio))
        r.update(result='independent_observer_inverse_precondition_known_passed',time_whitening_error=whitening,
            maximum_column_norm_error=float(abs(norms-1).max()),invertible_right_map_and_same_objective_verified=True,
            producer_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__))
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
