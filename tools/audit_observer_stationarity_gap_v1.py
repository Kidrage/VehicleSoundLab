"""Decimal gap/whitened-gradient identity controls, then the FROZEN old full case."""
import argparse, os, shutil, sys
from decimal import Decimal, localcontext
from pathlib import Path
from research_archive_v1 import load, save, sha


def decimal_identity(B0,L0,b0,q0,precision):
    with localcontext() as c:
        c.prec=precision
        def d(x):return Decimal.from_float(float(x))
        B,L=[[d(x) for x in row] for row in B0],[[d(x) for x in row] for row in L0]
        b,q=list(map(d,b0)),list(map(d,q0))
        def tr(A):return list(map(list,zip(*A)))
        def dot(x,y):return sum((a*b for a,b in zip(x,y)),Decimal(0))
        def mv(A,x):return [dot(r,x) for r in A]
        def mm(A,C):return [[dot(r,s) for s in tr(C)] for r in A]
        def solve(A,b):
            a=[r.copy()+[v] for r,v in zip(A,b)]
            for j in range(len(a)):
                pivot=max(range(j,len(a)),key=lambda k:abs(a[k][j]))
                a[j],a[pivot]=a[pivot],a[j]
                for k in range(j+1,len(a)):
                    f=a[k][j]/a[j][j]
                    for m in range(j,len(a)+1):a[k][m]-=f*a[j][m]
            x=[Decimal(0)]*len(a)
            for j in reversed(range(len(a))):x[j]=(a[j][-1]-dot(a[j][j+1:-1],x[j+1:]))/a[j][j]
            return x
        R=mm(L,tr(L))
        e=[v-w for v,w in zip(mv(B,q),b)]
        p=mv(tr(B),e)
        physical=[v+w for v,w in zip(p,mv(R,q))]
        white=solve(L,physical)
        displacement=[v+w for v,w in zip(q,solve(R,p))]
        positive_gap=dot(displacement,mv(R,displacement))
        squared_normal=dot(white,white)
        u=[-v for v in e]
        restored=solve(R,mv(tr(B),u))
        primal=dot(e,e)+dot(q,mv(R,q))
        dual=2*dot(b,u)-dot(u,u)-dot(restored,mv(R,restored))
        scale=max(Decimal(1),positive_gap)
        error=max(abs(positive_gap-squared_normal),abs(primal-dual-positive_gap))/scale
        assert error<Decimal('1e-60')
        return dict(positive_gap=positive_gap,squared_whitened_normal=squared_normal,
            primal_minus_dual=primal-dual,maximum_scaled_identity_error=error)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','original','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_supported_v1.full_oracle import FullOracle,vec
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',controls=[],sources={},inputs={})
    try:
        fixtures=(
            ('diagonal',[[1,.5],[.25,2],[0,1]],[[1,0],[0,.125]],[2,1,.125],[.25,-.5]),
            ('coupled',[[1,0,.5],[0,2,-.25],[.125,.5,1]],[[1,0,0],[.25,.125,0],[0,.5,1/32]],[2,1,.25],[.5,-.25,.125]),
            ('stationary',[[2,0],[0,4]],[[1,0],[0,.5]],[2.5,-8.125],[1,-2]),
            ('near_stationary',[[2,0],[0,4]],[[1,0],[0,.5]],[2.5,-8.125],[1+2**-35,-2-2**-40]),
            ('weak_prior_cancellation',[[1,1],[1,-1]],[[1,0],[0,2**-24]],[2**30+.25,2**30-.125],[2**30,.25]),
            ('zero',[[2,0],[0,4]],[[1,0],[0,.5]],[0,0],[0,0]))
        for label,B,L,b,q in fixtures:
            low,high=(decimal_identity(B,L,b,q,digits) for digits in (80,110))
            difference=max(abs(low[k]-high[k])/max(Decimal(1),abs(high[k])) for k in low)
            assert difference<Decimal('1e-50')
            r['controls'].append(dict(label=label,precision_digits=[80,110],precision_difference=float(difference),
                **{k:str(v) for k,v in high.items()}))
        source=load(a.original/'report.json')
        assert source['result']=='observer_representer_full_known_measured' and not source['solver_qualified']
        for path in (a.original/'report.json',a.original/'capture.npz'):
            r['inputs'][str(path)]=sha(path)
        assert r['inputs'][str(a.original/'capture.npz')]==source['capture_sha256']
        helpers=('tools/observer_supported_v1/full_oracle.py','tools/observer_supported_v1/audit_oracle.py',
            'tools/observer_frequency_v1/reduced_oracle.py','tools/observer_frequency_v1/audit_oracle.py','tools/observer_complete_v1/audit_oracle.py')
        for j,name in enumerate(helpers):
            shutil.copy2(repo/name,a.out/f'executed_oracle_{j}.py');r['sources'][name]=sha(repo/name)
        with np.load(a.original/'capture.npz') as z:
            oracle=FullOracle(z['audio'],z['positions'],z['orders'],z['scale'])
            q=z['fitted']/z['scale'][None]
            residual=oracle.data_forward(vec(q))-oracle.target()
            p=oracle.nodes(oracle.data_adjoint(residual))
            n=len(q);shape=q.shape;L=np.linalg.cholesky(oracle.R)
            def white(v):return linalg.solve_triangular(L,v.reshape(n,-1),lower=True).reshape(shape)
            normal_direct=white(p)+(L.T@q.reshape(n,-1)).reshape(shape)
            normal_original=white(p+(oracle.R@q.reshape(n,-1)).reshape(shape))
            displacement=q+linalg.solve(oracle.R,p.reshape(n,-1),assume_a='pos').reshape(shape)
            restored_normal=(L.T@displacement.reshape(n,-1)).reshape(shape)
            gap_direct=oracle.penalty(displacement)
            norm_squared=float(np.sum(abs(normal_direct)**2))
            def relative(x,y):return float(np.linalg.norm(x-y)/max(np.linalg.norm(y),1e-300))
            errors=dict(gap_vs_squared_whitened_normal=abs(gap_direct-norm_squared)/max(gap_direct,1e-300),
                original_gradient_ordering=relative(normal_original,normal_direct),
                restored_gradient_ordering=relative(restored_normal,normal_direct))
            assert max(errors.values())<2e-8,errors
            # Saved u was produced by another floating-point operator. Keep the
            # actual residual+u defect, rather than assuming it is exactly zero.
            u=z['u'];delta=residual+u
            saved_normal=(L.T@q.reshape(n,-1)).reshape(shape)-white(oracle.nodes(oracle.data_adjoint(u)))
            saved_gap=float(delta@delta)+float(np.sum(abs(saved_normal)**2))
            cert=source['representer_certificate']
            assert abs(saved_gap-cert['gap_upper_bound'])<2e-8*max(1.,cert['gap_upper_bound'])
            gap_gate=1e-6*cert['primal']+1e-10
            assert (saved_gap<=gap_gate)==cert['additional_gap_gate_passed']
            np.savez_compressed(a.out/'frozen_full_normals.npz',direct=normal_direct,original=normal_original,
                restored=restored_normal,saved_dual_normal=saved_normal,saved_residual_defect=delta)
            r.update(result='independent_observer_stationarity_gap_identity_passed',full_errors=errors,
                full_whitened_normal_norm=float(np.linalg.norm(normal_direct)),full_squared_whitened_normal=norm_squared,
                full_direct_residual_gap=gap_direct,full_saved_dual_gap=saved_gap,full_saved_gap_gate=gap_gate,
                full_saved_gap_passed=bool(saved_gap<=gap_gate),saved_residual_defect_norm=float(np.linalg.norm(delta)),
                full_capture_sha256=sha(a.out/'frozen_full_normals.npz'),only_frozen_old_full_case=True,
                new_solves=0,real_source_or_live_basis_read=False,live_solver_qualification_changed=False,
                floating_point_not_interval_proof=True,auditor_sha256=sha(__file__))
        save(a.out/'report.json',r)
        print(r['result'],r['full_errors'],'gap',r['full_saved_dual_gap'],'gate',r['full_saved_gap_gate'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':
    main()
