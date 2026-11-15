"""Independent scalar waves/frames and direct time solves audit source dual bounds."""
import argparse,os,shutil,sys,time
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','study','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--follow-pid',type=int);a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_complete_v1.follow import Follow
    from observer_complete_v1.audit_oracle import full_frame,curvature
    from observer_frequency_v1.audit_oracle import metric,frame_adjoint
    from observer_frequency_v1.reduced_oracle import synthesize,adjoint
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    helpers=('tools/observer_frequency_v1/audit_oracle.py','tools/observer_complete_v1/audit_oracle.py','tools/observer_complete_v1/follow.py','tools/observer_frequency_v1/reduced_oracle.py')
    for j,n in enumerate(helpers):shutil.copy2(repo/n,a.out/f'executed_oracle_{j}.py')
    r=dict(result='running',pid=os.getpid(),cases=[],maximum_scalar_error=0.)
    follow=Follow(a.study/'report.json',a.follow_pid)
    try:
        # Qualify the reduced-angle oracle on frozen short known sources and a
        # real-linear adjoint identity before evaluating any source bound.
        from observer_complete_v1.audit_oracle import synthesize as old_scalar
        rng=np.random.default_rng(95114);known_checks=[]
        known_root=a.workspace/'references/analysis/observer_frequency_correction_v1/known1'
        for name in ('separated.npz','neighbors.npz','stereo.npz'):
            with np.load(known_root/name) as z:
                nodes=z['nodes'];orders=z['orders'];positions=z['positions'];N=len(z['audio'])
                actual=synthesize(nodes,positions,orders,N);old=old_scalar(nodes,positions,orders,N)
                assert np.max(abs(actual-old))<2e-12
                test=rng.normal(size=actual.shape);g=adjoint(test,positions,orders)
                err=abs(np.vdot(test,actual).real-np.vdot(g,nodes).real)
                assert err<2e-10
                known_checks.append(dict(file=name,maximum_wave_error=float(np.max(abs(actual-old))),adjoint_dot_error=float(err)))
        r['reduced_oracle_known_controls']=known_checks
        record=follow.read()
        for n,d in record['sources'].items():assert sha(repo/n)==sha(a.study/'exact_sources'/n)==d
        for i in range(6):
            record,case=follow.case(i);row=dict(label=case['label'],variants={})
            folder=Path(case['variants']['initial']['path']).parent
            with np.load(folder/'source.npz') as z:audio,positions=z['audio'],z['positions']
            with np.load(folder/'scale.npz') as z:scale=z['scale']
            origin,_,weights,_,_=metric(audio,case['root_hz']);D=curvature(positions)
            R=.001*D.T@D+.000001*np.eye(len(positions))
            for tag,desc in case['variants'].items():
                path=Path(desc['path']);assert sha(path)==desc['sha256']
                with np.load(path) as z:nodes=z['nodes']
                wave=synthesize(nodes,positions,np.arange(1,289),len(audio))
                spectrum,cover=full_frame(wave);rows=spectrum-origin;weighted=rows*weights[None,:,None]
                p=adjoint(frame_adjoint(rows*weights[None,:,None]**2,cover,len(audio)),positions,np.arange(1,289))*scale[None]
                v=linalg.solve(R,p.reshape(len(positions),-1),assume_a='pos').reshape(p.shape)
                q=nodes/scale[None];cert=desc['certificate'];t=cert['residual_dual_scale']
                r2=float(np.sum(abs(weighted)**2));yr=float(np.vdot(origin*weights[None,:,None],weighted).real)
                pRp=float(np.vdot(p,v).real);dual=-(t*t)*(r2+pRp)-2*t*yr
                def penalty(q):return float(.001*np.sum(abs(D@q.reshape(len(q),-1))**2)+.000001*np.sum(abs(q)**2))
                primal=r2+penalty(q);gap=(1-t)**2*r2+penalty(q+t*v)
                for key,value in dict(primal=primal,dual_lower_bound=dual,gap_upper_bound=gap).items():
                    err=abs(value-cert[key])/max(1.,abs(value));r['maximum_scalar_error']=max(r['maximum_scalar_error'],err)
                    assert err<2e-8,(case['label'],tag,key,err)
                assert abs(primal-dual-gap)<2e-8*max(1.,primal)
                assert bool(gap<=1e-6*primal+1e-10)==cert['additional_gap_gate_passed']
                row['variants'][tag]=dict(primal=primal,gap_upper_bound=gap,relative_gap_upper_bound=gap/max(primal,1e-24))
            r['cases'].append(row);save(a.out/'report.json',r);print('AUDITED OPTIMALITY',case['label'],flush=True)
        record=follow.read()
        while record['result']=='running' and follow.alive():time.sleep(.1);record=follow.read()
        assert record['result']=='observer_frequency_optimality_all6_measured'
        for n,d in record['inputs'].items():assert sha(n)==d
        r.update(result='independent_observer_frequency_optimality_real_passed',producer_sha256=sha(a.study/'report.json'),
            gap_passed=record['gap_passed'],auditor_sha256=sha(__file__),oracles_sha256={n:sha(repo/n) for n in helpers})
        save(a.out/'report.json',r);print(r['result'],r['gap_passed'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise
    finally:follow.close()


if __name__=='__main__':main()
