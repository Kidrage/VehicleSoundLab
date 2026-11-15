"""Independent Decimal inverse actions, scalar QR and original correction gates."""
import argparse
import os
import shutil
import sys
from decimal import Decimal,localcontext
from pathlib import Path
from research_archive_v1 import load,save,sha


def decimal_inverse_solution(X0,b0,precision):
    with localcontext() as context:
        context.prec=precision
        X=[[Decimal.from_float(float(v)) for v in row] for row in X0]
        b=[[Decimal.from_float(float(v)) for v in row] for row in b0]
        n=len(X[0]);channels=len(b[0]);H=[]
        for i in range(n):
            H.append([sum((row[i]*row[j] for row in X),Decimal(int(i==j))) for j in range(n)]+b[i])
        for j in range(n):
            pivot=max(range(j,n),key=lambda k:abs(H[k][j]));H[j],H[pivot]=H[pivot],H[j]
            for i in range(j+1,n):
                ratio=H[i][j]/H[j][j]
                for k in range(j,n+channels):H[i][k]-=ratio*H[j][k]
        answer=[[Decimal(0)]*channels for i in range(n)]
        for i in range(n-1,-1,-1):
            for c in range(channels):
                answer[i][c]=(H[i][n+c]-sum((H[i][j]*answer[j][c] for j in range(i+1,n)),Decimal(0)))/H[i][i]
        return answer


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','study','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from audit_waveform_representer_controls_v1 import exact_solution
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    shutil.copy2(Path(__file__).with_name('audit_waveform_representer_controls_v1.py'),a.out/'executed_original_Decimal.py')
    r=dict(result='running',inverse_cases=[],original_cases=[],maximum_errors={})
    def check(name,x,y,gate=2e-12):
        x,y=np.asarray(x),np.asarray(y);assert x.shape==y.shape
        error=float(np.max(abs(x-y))/max(1.,abs(y).max()))
        r['maximum_errors'][name]=max(error,r['maximum_errors'].get(name,0.));assert error<gate,(name,error)
    def qmap(raw,tau,rhs,transpose=False):
        result=np.array(rhs,copy=True)
        for j in (range(len(tau)) if transpose else range(len(tau)-1,-1,-1)):
            v=np.r_[1.,raw[j+1:,j]]
            result[j:]-=v[:,None]*(tau[j]*(v@result[j:]))[None]
        return result
    def factors(z):
        assert ('inverse_inner_T' in z)==(source.get('inverse_backend','copy')=='copy')
        raw=z['x_raw'];m,n=raw.shape;k=min(raw.shape);F=np.triu(raw[:k])
        Q=qmap(raw,z['x_tau'],np.eye(m,k));check('X_Q_orthogonality',Q.T@Q,np.eye(k))
        right=z['inverse_right_raw'];Z=qmap(right,z['inverse_right_tau'],np.eye(n))
        check('right_full_Q_orthogonality',Z.T@Z,np.eye(n))
        R=np.triu(right[:k]);check('right_factor_identity',Z[:,:k]@R,F.T)
        inner=z['inverse_inner_raw'];T=z['inverse_inner_T'] if 'inverse_inner_T' in z else np.triu(inner[:k])
        U=qmap(inner,z['inverse_inner_tau'],np.eye(2*k,k))
        check('inner_factor_identity',U@T,np.vstack((np.eye(k),-R.T)))
        check('inner_Q_orthogonality',U.T@U,np.eye(k))
        def inverse(rhs):
            coords=Z.T@rhs
            coords[:k]=linalg.solve_triangular(T,linalg.solve_triangular(T,coords[:k],trans='T'))
            return Z@coords
        return Q,F,inverse
    def precision_agreement(low,high):
        difference=max(abs(x-y)/max(Decimal(1),abs(y)) for a,b in zip(low,high) for x,y in zip(a,b))
        assert difference<Decimal('1e-60');return str(difference)
    try:
        source=load(a.study/'report.json');assert source['result']=='waveform_original_correction_controls_measured'
        for n,h in source['sources'].items():assert sha(a.study/'exact_sources'/n)==h
        for case in source['inverse_cases']:
            path=a.study/case['file'];assert sha(path)==case['sha256']
            with np.load(path) as z:
                X,b,got=(z[n] for n in ('X','rhs','got'));n=X.shape[1]
                lo,hi=(decimal_inverse_solution(X,b,d) for d in (80,110));agreement=precision_agreement(lo,hi)
                exact=np.array([[float(v) for v in row] for row in hi])
                relative=float(np.linalg.norm(got-exact)/max(np.linalg.norm(exact),1e-300));assert relative<2e-7
                residual=X.T@(X@got)+got-b
                denominator=(np.linalg.norm(X)**2+1)*np.linalg.norm(got)+np.linalg.norm(b)
                backward=float(np.linalg.norm(residual)/max(denominator,1e-300));assert backward<1e-11
                check('inverse_adjoint',got[:,:n],got[:,:n].T)
                Q,F,inverse=factors(z);check('complete_X_reconstruction',Q@F,X)
                check('all_inverse_maps',inverse(b),got)
                assert np.count_nonzero(got[:,-1])==0
                assert case['factor']['identity_complement_directions']==n-min(X.shape)
                r['inverse_cases'].append(dict(label=case['label'],Decimal_precisions=[80,110],precision_agreement=agreement,
                    relative_error=relative,original_action_backward=backward,all_basis_and_independent_RHS_verified=True,qualified=True))
        for case in source['original_cases']:
            path=a.study/case['file'];assert sha(path)==case['sha256']
            with np.load(path) as z:
                P,W,R,y=(z[n] for n in ('Phi','W','R','y'));Lw=np.linalg.cholesky(W);Lr=np.linalg.cholesky(R)
                X=linalg.solve_triangular(Lr,(Lw.T@P).T,lower=True).T
                Q,F,inverse=factors(z);check('original_whitened_synthesis',Q@F,X)
                zs,es,gs=(z[n] for n in ('history_z','history_wave','history_original_normal'))
                assert len(zs)==len(es)==len(gs)==3 and len(z['delta_z'])==2
                check('initial_perturbation_z',zs[0],z['base_z']+z['initial_delta'])
                check('initial_consistent_wave',es[0],z['base_wave']+P@linalg.solve_triangular(Lr,z['initial_delta'],trans='T',lower=True))
                for j in range(3):
                    normal=linalg.solve_triangular(Lr,P.T@W@es[j],lower=True)+zs[j]
                    check('original_normal_each_step',gs[j],normal)
                    if j<2:
                        check('inverse_correction_each_step',z['delta_z'][j],-inverse(gs[j]))
                        check('node_update_each_step',zs[j+1],zs[j]+z['delta_z'][j])
                        check('wave_update_each_step',es[j+1],es[j]+P@linalg.solve_triangular(Lr,z['delta_z'][j],trans='T',lower=True))
                q=z['q'];check('corrected_z',z['z'],zs[-1]);check('corrected_wave',z['wave_model_residual'],es[-1])
                check('corrected_nodes',q,linalg.solve_triangular(Lr,z['z'],trans='T',lower=True))
                lo,hi=(exact_solution(P,W,R,y,d) for d in (80,110));agreement=precision_agreement(lo,hi)
                exact=np.array([[float(v) for v in row] for row in hi])
                relative=float(np.linalg.norm(q-exact)/max(np.linalg.norm(exact),1.));assert relative<2e-7
                model=Lw.T@es[-1];normA=np.sqrt(np.sum(X*X)+len(R));normr=np.sqrt(np.sum(model*model)+np.sum(z['z']**2))
                stable=float(np.linalg.norm(X.T@model+z['z'])/max(normA*normr,1e-300))
                backward=float(np.linalg.norm(X@z['z']-Lw.T@y-model)/max(np.linalg.norm(Lw.T@y),1e-300))
                e=P@q-y;gradient=P.T@W@e+R@q
                stationarity=float(np.linalg.norm(gradient)/max(np.linalg.norm(P.T@W@y),1e-300))
                J=float(np.sum(e*(W@e))+np.sum(q*(R@q)))
                delta=q+linalg.solve(R,P.T@W@e,assume_a='pos');gap=float(np.sum(delta*(R@delta)))
                u=-model;data=Lw.T@e;delta2=q-linalg.solve(R,(Lw.T@P).T@u,assume_a='pos')
                gap2=float(np.sum((data+u)**2)+np.sum(delta2*(R@delta2)))
                qualified=bool(stationarity<2e-7 and stable<=1e-11 and backward<=1e-11 and gap<=1e-6*J+1e-10 and gap2<=1e-6*J+1e-10)
                assert qualified,(case['label'],stationarity,stable,backward,gap,gap2)
                r['original_cases'].append(dict(label=case['label'],Decimal_precisions=[80,110],precision_agreement=agreement,
                    relative_error=relative,original_gradient=stationarity,stable_complete_normal=stable,backward=backward,
                    residual_gap=gap,representer_gap=gap2,original_gap_gate=1e-6*J+1e-10,qualified=True))
                print('AUDITED CORRECTION',case['label'],stable,flush=True)
        assert len(r['inverse_cases'])==8 and len(r['original_cases'])==7
        r.update(result='independent_waveform_original_correction_controls_passed',all_qualified=True,
            inverse_backend=source.get('inverse_backend','copy'),
            producer_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__),no_original12_or_shared8_or_source_or_runtime_qualification=True)
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
