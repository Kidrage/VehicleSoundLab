"""Audit historical original captures against their executed-source snapshots."""
import argparse,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_inverse_v1.audit_oracle import render_groups,observe,objective_gradient
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    helpers=('tools/observer_inverse_v1/audit_oracle.py','tools/observer_forward_v1/audit_oracle.py',
             'tools/circular_phase_lift_v1/audit_oracle.py')
    for j,name in enumerate(helpers):shutil.copy2(repo/name,a.out/f'executed_oracle_{j}.py')
    r=dict(result='running',cases=[],captures=0,Gram_matrices=0,maximum_wave_error=0.,
        maximum_Gram_scaled_error=0.,historical_sources_different_from_current=[])
    try:
        producer=load(a.study/'report.json')
        assert producer['result']=='observer_inverse_all6_measured' and len(producer['cases'])==6
        for name,digest in producer['sources'].items():
            assert sha(a.study/'exact_sources'/name)==digest
            if sha(repo/name)!=digest:r['historical_sources_different_from_current'].append(name)
        for path,digest in producer['inputs'].items():assert sha(path)==digest
        for case in producer['cases']:
            folder=a.study/case['label'];assert sha(folder/'source.npz')==case['source_sha256']
            with np.load(folder/'source.npz') as z:
                audio,target,positions=z['audio'],z['coefficients'],z['positions']
            assert sha(folder/'scale.npz')==case['scale_sha256']
            with np.load(folder/'scale.npz') as z:scale=z['scale']
            for name,desc in case['variants'].items():
                path=folder/desc['file'];assert sha(path)==desc['sha256']
                with np.load(path) as z:
                    wave=render_groups(z['nodes'],positions,case['root_hz'],producer['carrier_edges'],len(audio))
                    err=float(abs(wave-z['grouped_audio']).max());assert err<2e-10
                    r['maximum_wave_error']=max(r['maximum_wave_error'],err)
                    assert np.array_equal(z['audio'],z['grouped_audio'].sum(axis=1))
                    measured=observe(z['grouped_audio'],case['root_hz'],producer['bands'])
                    assert abs(measured['coefficients']-z['coefficients']).max()<2e-10
                    for prefix in ('line','broad'):
                        m=measured[prefix+'_Gram']
                        normalization=np.maximum(np.diagonal(m,axis1=-2,axis2=-1).real.sum(axis=-1).max(axis=0),1e-24)
                        err=float((abs(m-z[prefix+'_Gram'])/normalization[None,:,None,None]).max());assert err<2e-10
                        r['maximum_Gram_scaled_error']=max(r['maximum_Gram_scaled_error'],err)
                        r['Gram_matrices']+=len(m)*len(producer['bands'])
                    norm=max(float(abs(measured['time_energy_Gram']).max()),1e-24)
                    assert abs(measured['all_frequency_Gram'].real-measured['time_energy_Gram']).max()/norm<2e-9
                    for key in ('all_frequency_Gram','time_energy_Gram'):assert abs(measured[key]-z[key]).max()/norm<2e-9
                    objective,stationarity,_=objective_gradient(z['nodes'],positions,scale,target,measured['coefficients'])
                    expected=case['solve']['objective'] if name=='inverse' else case['baseline_objective']
                    assert abs(objective-expected)<2e-8*max(1,expected)
                    if name=='inverse':
                        assert abs(stationarity-case['solve']['relative_stationarity'])<2e-9
                        assert bool(case['solve']['stop'] in (1,2,4,5) and stationarity<2e-7)==case['solve']['converged']
                r['captures']+=1;print('AUDITED original inverse',case['label'],name,flush=True)
            r['cases'].append(case['label']);save(a.out/'report.json',r)
        assert r['captures']==12 and r['Gram_matrices']==5760
        r.update(result='independent_observer_inverse_original_passed',all_converged=producer['all_converged'],
            producer_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__),
            oracles_sha256={n:sha(repo/n) for n in helpers})
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
