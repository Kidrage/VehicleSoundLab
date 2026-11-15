"""Independent Decimal original solves, scalar DFT and full Kronecker roots."""
import argparse
import math
import os
import shutil
import sys
from pathlib import Path
from decimal import Decimal
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','study','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from audit_waveform_representer_controls_v1 import exact_solution
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    shutil.copy2(repo/'tools/audit_waveform_representer_controls_v1.py',a.out/'executed_decimal_oracle.py')
    source=load(a.study/'report.json');r=dict(result='running',cases=[],frames=[],temporal=[],maximum_errors={})
    def check(n,x,y,scale=1.,gate=2e-8):
        x,y=np.asarray(x),np.asarray(y);assert x.shape==y.shape,(n,x.shape,y.shape)
        err=float(np.max(abs(x-y))/scale);r['maximum_errors'][n]=max(err,r['maximum_errors'].get(n,0.))
        assert err<gate,(n,err)
    try:
        assert source['result']=='waveform_structured_controls_measured'
        for n,h in source['sources'].items():assert sha(a.study/'exact_sources'/n)==h
        for case in source['cases']:
            path=a.study/case['file'];assert sha(path)==case['sha256']
            with np.load(path) as z:
                P,W,R,y=(z[n] for n in ('Phi','W','R','y'))
                lo,hi=(exact_solution(P,W,R,y,d) for d in (80,110))
                difference=max(abs(x-y) for a,b in zip(lo,hi) for x,y in zip(a,b));assert difference<Decimal('1e-60')
                exact=np.array([[float(v) for v in row] for row in hi])
                relative=float(np.linalg.norm(z['q']-exact)/max(np.linalg.norm(exact),1.));assert relative<2e-7
                Lw=np.linalg.cholesky(W);Lr=np.linalg.cholesky(R)
                X=linalg.solve_triangular(Lr,(Lw.T@P).T,lower=True).T
                check('packed_root_recovery',linalg.solve_triangular(Lr.T,z['z']),z['q'])
                model=z['root_model_residual'];normal=X.T@model+z['z']
                check('wave_root_mapping',Lw.T@z['wave_model_residual'],model,max(1.,np.linalg.norm(y)))
                check('full_model_normal',normal,z['stable_root_normal'],max(1.,np.linalg.norm(y)))
                normA=np.sqrt(np.sum(X*X)+len(R));normr=np.sqrt(np.sum(model*model)+np.sum(z['z']**2))
                normal_ratio=float(np.linalg.norm(normal)/max(normA*normr,1e-300))
                backward=float(np.linalg.norm(X@z['z']-Lw.T@y-model)/max(np.linalg.norm(Lw.T@y),1e-300))
                assert normal_ratio<=1e-11 and backward<=1e-11
                e=P@z['q']-y;delta=z['q']+linalg.solve(R,P.T@W@e,assume_a='pos')
                J=float(np.sum(e*(W@e))+np.sum(z['q']*(R@z['q'])))
                gap=float(np.sum(delta*(R@delta)));assert gap<=1e-6*J+1e-10
                assert all(v['stable_root_guard_passed'] for v in case['info'])
                r['cases'].append(dict(label=case['label'],Decimal_precisions=[80,110],precision_difference=str(difference),
                    dense_error=relative,complete_model_normal=normal_ratio,backward=backward,original_gap=gap,qualified=True))
        for case in source['frames']:
            path=a.study/case['file'];assert sha(path)==case['sha256']
            with np.load(path) as z:
                N=len(z['W']);size=len(z['window']);rows=[]
                for start in z['starts']:
                    for k in range(size//2+1):
                        row=np.zeros(N,complex)
                        factor=float(z['amplitude'])*float(z['weights'][k])*math.sqrt(1 if k in (0,size//2) else 2)/math.sqrt(size)
                        for j in range(size):
                            phase=-2*math.pi*k*j/size
                            row[int(start)+j]=factor*float(z['window'][j])/math.sqrt(float(z['coverage'][int(start)+j]))*complex(math.cos(phase),math.sin(phase))
                        rows.extend((row.real,row.imag))
                A=np.array(rows);W=np.eye(N)/float(z['sigma'])**2+A.T@A
                check('full_DFT_'+case['label'],W,z['W'],max(1.,abs(W).max()),gate=2e-12)
                check('DFT_root_'+case['label'],z['L']@z['L'].T,W,max(1.,abs(W).max()),gate=2e-12)
                r['frames'].append(dict(label=case['label'],all_entries=N*N,qualified=True))
        for case in source['temporal']:
            path=a.study/case['file'];assert sha(path)==case['sha256']
            with np.load(path) as z:
                M,H,C=map(int,z['shape']);K=.001*z['D'].T@z['D']+.000001*np.eye(M)
                R=linalg.block_diag(np.kron(K,np.eye(H*C)),np.kron(K,np.eye(H*C)))
                L=np.linalg.cholesky(R);p=z['probes']
                for n,expected in (('root',L@p),('root_transpose',L.T@p),('inverse',linalg.solve_triangular(L,p,lower=True)),
                    ('inverse_transpose',linalg.solve_triangular(L.T,p,lower=False)),('apply',R@p)):
                    check('temporal_'+n,z[n],expected,max(1.,np.linalg.norm(expected)),gate=2e-12)
                check('temporal_energy',np.sum(p*(R@p),axis=0),np.sum(z['root_transpose']**2,axis=0),gate=2e-12)
                if C==2:
                    for n in ('root','root_transpose','inverse','inverse_transpose','apply'):
                        assert np.count_nonzero(z[n][:,1].reshape(2,M,H,C)[:,:,:,1])==0
                r['temporal'].append(dict(label=case['label'],all_packed_root_maps_passed=True,stereo_no_crosstalk=True,qualified=True))
        assert len(r['cases'])==7 and len(r['frames'])==4 and len(r['temporal'])==3
        r.update(result='independent_waveform_structured_controls_passed',all_qualified=True,
            producer_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__),
            source_or_full_or_runtime_qualified=False)
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
