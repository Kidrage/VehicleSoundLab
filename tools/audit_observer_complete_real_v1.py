"""Independent all-source complete objective and old-window/weak-band audit."""
import argparse,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--follow-pid',type=int);a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_complete_v1.follow import Follow
    from observer_complete_v1.audit_oracle import full_frame,objective_gradient,curvature
    from observer_complete_v1.audit_capture import compare
    from observer_inverse_v1.audit_oracle import render_groups,observe
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    helpers=('tools/observer_complete_v1/audit_oracle.py','tools/observer_complete_v1/audit_capture.py',
        'tools/observer_complete_v1/follow.py','tools/observer_inverse_v1/audit_oracle.py',
        'tools/circular_phase_lift_v1/audit_oracle.py')
    shutil.copy2(__file__,a.out/'executed_audit.py')
    for j,name in enumerate(helpers):shutil.copy2(repo/name,a.out/f'executed_oracle_{j}.py')
    follow=Follow(a.study/'report.json',a.follow_pid)
    r=dict(result='running',pid=os.getpid(),cases=[],captures=0,band_Gram_matrices=0,maximum_errors={},maximum_wave_error=0.)
    try:
        producer=follow.read()
        for name,digest in producer['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
        parent=a.workspace/'baselines/observer_inverse_v1/evidence/real2'
        for i in range(6):
            producer,case=follow.case(i);label=case['label'];folder=a.study/label
            assert sha(folder/'source.npz')==case['source_sha256'] and sha(folder/'scale.npz')==case['scale_sha256']
            with np.load(folder/'source.npz') as z,np.load(parent/label/'source.npz') as old:
                assert z.files==old.files and all(np.array_equal(z[k],old[k]) for k in z.files)
                audio,target,positions=z['audio'],z['coefficients'],z['positions']
                measured=observe(audio[:,None,:],case['root_hz'],producer['bands']);compare(measured,z,r)
            with np.load(folder/'scale.npz') as z:
                amp=np.sqrt(np.mean(abs(target)**2,axis=(0,2)));scale=np.maximum(amp,amp.max()*1e-6)[:,None]
                assert np.array_equal(scale,z['scale'])
            sigma=float(np.sqrt(np.mean(audio**2)));assert sigma==case['wave_scale']
            D=curvature(positions);row=dict(label=label,variants={})
            for name,desc in case['variants'].items():
                path=folder/desc['file'];assert sha(path)==desc['sha256']
                with np.load(path) as z:
                    grouped=render_groups(z['nodes'],positions,case['root_hz'],producer['carrier_edges'],len(audio))
                    err=float(abs(grouped-z['grouped_audio']).max());assert err<2e-10
                    r['maximum_wave_error']=max(r['maximum_wave_error'],err)
                    assert np.array_equal(z['audio'],z['grouped_audio'].sum(axis=1))
                    measured=observe(z['grouped_audio'],case['root_hz'],producer['bands']);compare(measured,z,r)
                    q=z['nodes']/scale[None];d=D@q.reshape(len(q),-1);res=z['audio']-audio
                    objective=float(np.sum(res**2)/sigma**2+.001*np.sum(abs(d)**2)+.000001*np.sum(abs(q)**2))
                    assert abs(objective-desc['new_objective'])<2e-8*max(1,objective),(label,name,objective,desc['new_objective'])
                    nrmse=float(np.linalg.norm(res)/np.linalg.norm(audio));assert abs(nrmse-float(z['wave_NRMSE']))<2e-12
                    if name=='complete':
                        value,stationarity=objective_gradient(z['nodes'],positions,scale,sigma,audio)
                        assert abs(value-objective)<2e-8*max(1,objective)
                        assert abs(stationarity-case['solve']['relative_stationarity'])<2e-9
                        assert case['solve']['converged']==bool(case['solve']['stop'] in (1,2,4,5) and stationarity<2e-7)
                        spectrum,coverage=full_frame(res)
                        assert abs(coverage-z['complete_coverage']).max()<2e-14 and (coverage>0).all()
                        energy=float(np.sum(abs(spectrum)**2));wave=float(np.sum(res**2))
                        assert abs(energy-wave)<2e-10*max(wave,1e-24)
                        assert abs(energy-float(z['complete_frame_error_energy']))<2e-10*max(wave,1e-24)
                        assert abs(wave-float(z['complete_wave_error_energy']))<2e-12
                        row['stationarity']=stationarity;row['solver_converged']=case['solve']['converged']
                    row['variants'][name]=dict(new_objective=objective,wave_NRMSE=nrmse)
                r['captures']+=1;print('AUDITED complete source',label,name,flush=True)
            r['cases'].append(row);save(a.out/'report.json',r)
        producer=follow.read();assert producer['result']=='observer_complete_all6_measured'
        for path,digest in producer['inputs'].items():assert sha(path)==digest
        assert r['captures']==24 and r['band_Gram_matrices']==11520
        r.update(result='independent_observer_complete_real_passed',all_converged=producer['all_converged'],
            producer_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__),
            oracles_sha256={n:sha(repo/n) for n in helpers},not_stochastic_source_or_timbre_qualification=True)
        save(a.out/'report.json',r);print(r['result'],'all_converged',r['all_converged'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise
    finally:follow.close()


if __name__=='__main__':main()
