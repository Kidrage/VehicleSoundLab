"""Explicit matrices/dense optima independently bound every known candidate."""
import argparse,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','study','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_frequency_v1.audit_oracle import matrices,metric
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    helpers=('tools/observer_frequency_v1/audit_oracle.py','tools/observer_complete_v1/audit_oracle.py')
    for j,n in enumerate(helpers):shutil.copy2(repo/n,a.out/f'executed_oracle_{j}.py')
    r=dict(result='running',cases=[],material_read=False)
    try:
        source=load(a.study/'report.json');assert source['result']=='observer_frequency_optimality_known_ready'
        for n,d in source['sources'].items():assert sha(repo/n)==sha(a.study/'exact_sources'/n)==d
        for n,d in source['inputs'].items():assert sha(n)==d
        for case in source['cases']:
            path=a.study/case['file'];assert sha(path)==case['sha256']
            with np.load(path) as z:
                _,_,w,_,_=metric(z['audio'],64.);assert np.max(abs(w-z['weights']))<2e-9*max(1.,w.max())
                r2=yr=pRp=primal=optimum=0.;parts=[]
                for c in range(z['audio'].shape[1]):
                    systems,_,_=matrices(z['positions'],z['orders'],z['scale'],z['audio'][:,c:c+1],w,1.)
                    A,b=systems['weighted_frame'];q=z['nodes'][:,:,c]/z['scale'][:,0][None]
                    x=np.r_[q.real.ravel(),q.imag.ravel()]
                    # Frame rows are followed by D2/ridge rows; independent
                    # fixture dimensions, not a production system property.
                    # Count original full-frame starts directly to avoid an
                    # off-by-one at non-multiple record lengths.
                    data_rows=2*len(range(-3840,len(z['audio']),256))*2049
                    B,y=A[:data_rows],b[:data_rows];tail=A[data_rows:]
                    R=tail.T@tail;res=B@x-y;pvec=B.T@res;v=linalg.solve(R,pvec,assume_a='pos')
                    r2+=float(res@res);yr+=float(y@res);pRp+=float(pvec@v)
                    primal+=float(np.sum((A@x-b)**2))
                    exact=linalg.lstsq(A,b,lapack_driver='gelsd')[0];optimum+=float(np.sum((A@exact-b)**2))
                    parts.append((res,x,v,R))
                den=r2+pRp;best_t=-yr/den if den else 0.
                # A feasible dual point does not need to be optimal on its ray.
                # Near a dense optimum, columnwise FFT roundoff perturbs the
                # independently best t more than the resulting gap. Validate
                # the ACTUAL reported dual point at the original gap gates.
                t=case['certificate']['residual_dual_scale'];dual=-(t*t)*den-2*t*yr
                gap=sum(float((1-t)**2*(res@res)+(x+t*v)@R@(x+t*v)) for res,x,v,R in parts)
                cert=case['certificate']
                for key,value in dict(primal=primal,dual_lower_bound=dual,gap_upper_bound=gap).items():
                    assert abs(value-cert[key])<2e-8*max(1.,abs(value)),(case['label'],key,value,cert[key])
                assert dual<=optimum+2e-8*max(1.,optimum)
                assert primal-optimum<=gap+2e-8*max(1.,primal)
                assert abs((primal-dual)-gap)<2e-8*max(1.,primal)
                gate=bool(gap<=1e-6*primal+1e-10);assert gate==cert['additional_gap_gate_passed']
                assert cert['original_LSMR_gate_unchanged'] and cert['floating_point_not_interval_certificate']
                r['cases'].append(dict(label=case['label'],true_suboptimality=primal-optimum,
                    gap_upper_bound=gap,gate=gate,reported_feasible_dual_scale=t,
                    independent_best_ray_scale=best_t,ray_scale_difference=best_t-t))
        r.update(result='independent_observer_frequency_optimality_known_passed',producer_sha256=sha(a.study/'report.json'),
            auditor_sha256=sha(__file__),oracles_sha256={n:sha(repo/n) for n in helpers})
        save(a.out/'report.json',r);print(r['result'],len(r['cases']),flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
