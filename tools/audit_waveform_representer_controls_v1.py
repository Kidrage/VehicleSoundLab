"""Independent Decimal original solutions and explicit real DFT Gram controls."""
import argparse, math, os, shutil, sys
from decimal import Decimal, localcontext
from pathlib import Path
from research_archive_v1 import load, save, sha


def exact_solution(Phi0,W0,R0,y0,precision):
    with localcontext() as context:
        context.prec=precision
        def d(x):return Decimal.from_float(float(x))
        def transpose(A):return list(map(list,zip(*A)))
        def dot(a,b):return sum((x*y for x,y in zip(a,b)),Decimal(0))
        def mm(A,B):return [[dot(a,b) for b in transpose(B)] for a in A]
        P,W,R,y=([[d(v) for v in row] for row in A] for A in (Phi0,W0,R0,y0))
        H=mm(transpose(P),mm(W,P));target=mm(transpose(P),mm(W,y))
        for i in range(len(H)):
            for j in range(len(H)):H[i][j]+=R[i][j]
        H=[row+rhs for row,rhs in zip(H,target)]
        n=len(H);channels=len(y[0])
        for j in range(n):
            pivot=max(range(j,n),key=lambda k:abs(H[k][j]))
            H[j],H[pivot]=H[pivot],H[j]
            for i in range(j+1,n):
                factor=H[i][j]/H[j][j]
                for k in range(j,n+channels):H[i][k]-=factor*H[j][k]
        result=[[Decimal(0)]*channels for _ in range(n)]
        for i in reversed(range(n)):
            for c in range(channels):
                result[i][c]=(H[i][n+c]-sum((H[i][j]*result[j][c] for j in range(i+1,n)),Decimal(0)))/H[i][i]
        return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',cases=[],frames=[],maximum_errors={})
    def check(name,x,y,scale=1.,gate=2e-8):
        x,y=np.asarray(x),np.asarray(y)
        assert x.shape==y.shape,(name,x.shape,y.shape)
        e=float(np.max(abs(x-y))/scale)
        r['maximum_errors'][name]=max(e,r['maximum_errors'].get(name,0.))
        assert e<gate,(name,e)
    try:
        source=load(a.study/'report.json')
        assert source['result']=='waveform_representer_explicit_measured'
        for name,digest in source['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
        for case in source['cases']:
            path=a.study/case['file'];assert sha(path)==case['sha256']
            with np.load(path) as z:
                P,W,R,y=(z[n] for n in ('Phi','W','R','y'))
                low,high=(exact_solution(P,W,R,y,digits) for digits in (80,110))
                difference=max(abs(x-y)/max(Decimal(1),abs(y)) for row1,row2 in zip(low,high) for x,y in zip(row1,row2))
                assert difference<Decimal('1e-60')
                exact=np.array([[float(v) for v in row] for row in high])
                relative=float(np.linalg.norm(z['q']-exact)/max(np.linalg.norm(exact),1.))
                assert relative<2e-7
                Lw=np.linalg.cholesky(W);Lr=np.linalg.cholesky(R)
                A=np.vstack((Lw.T@P,Lr.T));b=np.vstack((Lw.T@y,np.zeros((len(R),y.shape[1]))))
                dense=linalg.lstsq(A,b,lapack_driver='gelsd')[0]
                check('dense_original_solution',dense,exact,max(1.,np.linalg.norm(exact)))
                check('direct_QR_solution',z['q'],exact,max(1.,np.linalg.norm(exact)))
                X=(linalg.solve_triangular(Lr,(Lw.T@P).T,lower=True)).T
                check('full_weighted_synthesis',X,z['X'],max(1.,abs(X).max()))
                check('QR_synthesis_identity',z['Q']@z['F'],X,max(1.,abs(X).max()))
                check('QR_orthogonality',z['Q'].T@z['Q'],np.eye(z['Q'].shape[1]),gate=2e-12)
                assert z['Q'].shape[1]==min(P.shape)
                check('recover_nodes',linalg.solve_triangular(Lr.T,z['z']),z['q'])
                check('wave_dual_identity',(np.eye(len(y))+X@X.T)@z['v'],Lw.T@y,max(1.,np.linalg.norm(Lw.T@y)))
                C=P@linalg.solve(R,P.T,assume_a='pos')
                check('wave_covariance',(Lw.T@C@Lw),X@X.T,max(1.,abs(X@X.T).max()))
                q=z['q'];e=P@q-y;g=P.T@W@e+R@q
                primal=float(np.sum(e*(W@e))+np.sum(q*(R@q)))
                displacement=q+linalg.solve(R,P.T@W@e,assume_a='pos')
                gap=float(np.sum(displacement*(R@displacement)))
                assert gap<=1e-6*primal+1e-10
                if 'root_model_residual' in z:
                    # Independent SVD complement of the SMALL dual system;
                    # check the complete primal normal, not just F^T residual.
                    F,Q=z['F'],z['Q'];k=len(F)
                    c=Q.T@(Lw.T@y)
                    if 'reduced_primal_model_residual' in z:
                        B=np.vstack((F,np.eye(len(R))))
                        rhs=np.vstack((c,np.zeros((len(R),y.shape[1]))))
                        complement=linalg.null_space(B.T)
                        reduced=-complement@(complement.T@rhs)
                        check('independent_primal_residual',reduced,z['reduced_primal_model_residual'],max(1.,np.linalg.norm(rhs)))
                        check('nodes_from_same_residual',z['reduced_primal_model_residual'][k:],z['z'])
                        check('nullspace_identity',B.T@z['nullspace_generators'],np.zeros((len(R),k)),gate=2e-12)
                    else:
                        dual=np.vstack((F.T,np.eye(k)))
                        dual_target=np.vstack((np.zeros((len(R),y.shape[1])),c))
                        complement=linalg.null_space(dual.T)
                        dual_model=-complement@(complement.T@dual_target)
                        check('independent_dual_residual',dual_model,z['dual_model_residual'],max(1.,np.linalg.norm(dual_target)))
                    model=z['root_model_residual']
                    check('model_waveform_mapping',Lw.T@z['wave_model_residual'],model,max(1.,np.linalg.norm(Lw.T@y)))
                    normal=X.T@model+z['z']
                    check('complete_stable_normal',normal,z['stable_root_normal'])
                    normA=np.sqrt(np.sum(X*X)+len(R));normr=np.sqrt(np.sum(model*model)+np.sum(z['z']**2))
                    ratio=float(np.linalg.norm(normal)/max(normA*normr,1e-300))
                    discrepancy=float(np.linalg.norm(X@z['z']-Lw.T@y-model)/max(np.linalg.norm(Lw.T@y),1e-300))
                    assert ratio<=1e-11 and discrepancy<=1e-11
                    assert case['info']['stable_root_guard_passed']
                r['cases'].append(dict(label=case['label'],Decimal_precisions=[80,110],precision_difference=str(difference),
                    dense_relative_error=relative,objective=primal,original_gap=gap,
                    original_gradient_norm=float(np.linalg.norm(g)),qualified=True,
                    direct_normal_passed=case['info']['original_direct_whitened_normal_passed']))
        for case in source['frames']:
            path=a.study/case['file'];assert sha(path)==case['sha256']
            with np.load(path) as z:
                N=len(z['W']);size=len(z['window']);rows=[]
                for start in z['starts']:
                    for k in range(size//2+1):
                        row=np.zeros(N,complex)
                        normalization=float(z['amplitude'])*float(z['weights'][k])*math.sqrt(1 if k in (0,size//2) else 2)/math.sqrt(size)
                        for j in range(size):
                            angle=-2*math.pi*k*j/size
                            row[int(start)+j]=normalization*float(z['window'][j])/math.sqrt(float(z['coverage'][int(start)+j]))*complex(math.cos(angle),math.sin(angle))
                        rows.extend((row.real,row.imag))
                M=np.asarray(rows)
                W=np.eye(N)/float(z['sigma'])**2+M.T@M
                check('all_entry_'+case['label']+'_finite_DFT_Gram',W,z['W'],max(1.,abs(W).max()),gate=2e-12)
                r['frames'].append(dict(label=case['label'],all_entries=N*N,qualified=True))
        assert len(r['cases'])==7 and len(r['frames'])==4
        r.update(result='independent_waveform_representer_explicit_passed',all_qualified=True,
            producer_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__),
            source_or_old12_or_full_or_runtime_qualified=False)
        save(a.out/'report.json',r);print(r['result'],r['cases'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
