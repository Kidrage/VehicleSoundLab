"""Independent ALL6 capture/observer/signed-Gram/objective audit, optional follow."""
import argparse,json,os,shutil,sys,time
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','study','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--follow-pid',type=int);a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_inverse_v1.audit_oracle import render_groups,observe,objective_gradient,statistics
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    helpers=('tools/observer_inverse_v1/audit_oracle.py','tools/observer_forward_v1/audit_oracle.py','tools/circular_phase_lift_v1/audit_oracle.py')
    shutil.copy2(__file__,a.out/'executed_audit.py')
    for j,name in enumerate(helpers):shutil.copy2(repo/name,a.out/f'executed_oracle_{j}.py')
    r=dict(result='running',pid=os.getpid(),cases=[],captures=0,band_Gram_matrices=0,maximum_wave_error=0.,maximum_observer_error=0.,maximum_Gram_scaled_error=0.,maximum_stats_error=0.)
    kernel=None;handle=None
    try:
        if a.follow_pid:
            import ctypes
            from ctypes import wintypes
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.OpenProcess.argtypes=(wintypes.DWORD,wintypes.BOOL,wintypes.DWORD);kernel.OpenProcess.restype=wintypes.HANDLE
            kernel.GetExitCodeProcess.argtypes=(wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD));kernel.GetExitCodeProcess.restype=wintypes.BOOL
            kernel.CloseHandle.argtypes=(wintypes.HANDLE,);kernel.CloseHandle.restype=wintypes.BOOL
            handle=kernel.OpenProcess(0x1000,False,a.follow_pid)
        def alive():
            if not handle:return False
            code=wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)):raise ctypes.WinError(ctypes.get_last_error())
            return code.value==259
        def read():
            while True:
                try:return load(a.study/'report.json')
                except (FileNotFoundError,json.JSONDecodeError):
                    if not alive():raise
                    time.sleep(.2)
        producer=read()
        for name,d in producer['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==d
        geometry=a.workspace/'baselines/coefficient_geometry_v1/evidence/real1';parent=a.workspace/'baselines/conditional_phase_time_v1/evidence/real1'
        def stats_check(truth,z,prefix):
            for f in ('mean','CV','complex_coherence','covariance','mid_power','side_power','lag_covariance'):
                x=truth[f];y=z[prefix+f]
                if f=='covariance' or f=='lag_covariance':scale=max(float(abs(x).max()),1e-24)
                elif f in ('mean','mid_power','side_power'):scale=max(float(abs(x).max()),1e-24)
                else:scale=1.
                err=float(abs(x-y).max()/scale);assert err<2e-9,(prefix,f,err);r['maximum_stats_error']=max(r['maximum_stats_error'],err)
        for i in range(6):
            while True:
                producer=read()
                if len(producer['cases'])>i:break
                if not alive():
                    producer=read()
                    if len(producer['cases'])>i:break
                    raise RuntimeError('Producer terminal before expected source')
                time.sleep(.25)
            case=producer['cases'][i];label=case['label'];folder=a.study/label;root=case['root_hz'];bands=producer['bands'];edges=producer['carrier_edges']
            assert sha(folder/'source.npz')==case['source_sha256'] and sha(folder/'scale.npz')==case['scale_sha256']
            with np.load(folder/'source.npz') as source,np.load(geometry/label/'source.npz') as geom,np.load(parent/label/'source.npz') as old:
                assert np.array_equal(source['audio'],geom['rebuilt']) and np.array_equal(source['audio'],old['audio'])
                assert np.array_equal(source['native'],geom['native']) and np.array_equal(source['coordinates'],geom['positions'])
                audio=source['audio'];target=source['coefficients'];positions=source['positions'];assert np.array_equal(target,old['coefficients'])
                observed=observe(audio[:,None,:],root,bands);assert abs(observed['coefficients']-target).max()<2e-10
                for prefix,pk,ck in (('line','power','cross'),('broad','broadband_power','broadband_cross')):stats_check(statistics(observed[pk],observed[ck]),source,prefix+'_')
            with np.load(folder/'scale.npz') as z:
                amp=np.sqrt(np.mean(abs(target)**2,axis=(0,2)));scale=np.maximum(amp,amp.max()*1e-6)[:,None]
                assert np.array_equal(scale,z['scale']) and int((amp<amp.max()*1e-6).sum())==case['floored_orders']
            verified=dict(label=label,variants={},solve_converged=case['solve']['converged'])
            for name,desc in case['variants'].items():
                path=folder/desc['file'];assert sha(path)==desc['sha256']
                with np.load(path) as z:
                    grouped=render_groups(z['nodes'],positions,root,edges,len(audio));err=float(abs(grouped-z['grouped_audio']).max());assert err<2e-10
                    r['maximum_wave_error']=max(r['maximum_wave_error'],err);assert np.array_equal(z['grouped_audio'].sum(axis=1),z['audio'])
                    measured=observe(z['grouped_audio'],root,bands);err=float(abs(measured['coefficients']-z['coefficients']).max());assert err<2e-10
                    r['maximum_observer_error']=max(r['maximum_observer_error'],err)
                    for prefix,pk,ck in (('line','power','cross'),('broad','broadband_power','broadband_cross')):
                        m=measured[prefix+'_Gram'];ref=np.maximum(np.diagonal(m,axis1=-2,axis2=-1).real.sum(axis=-1).max(axis=0),1e-24)
                        err=float((abs(m-z[prefix+'_Gram'])/ref[None,:,None,None]).max());assert err<2e-10;r['maximum_Gram_scaled_error']=max(r['maximum_Gram_scaled_error'],err)
                        stats_check(statistics(measured[pk],measured[ck]),z,prefix+'_')
                        slices=np.array_split(np.arange(len(measured[pk])),3);assert np.array_equal(z['chunk_rows'],[len(s) for s in slices])
                        for f in ('mean','CV','complex_coherence'):
                            truth=np.stack([statistics(measured[pk][s],measured[ck][s])[f] for s in slices]);sc=max(float(abs(truth).max()),1e-24)
                            assert abs(truth-z['chunks_'+prefix+'_'+f]).max()/sc<2e-9
                        # Direct per-frame signed partition, independently summed.
                        mean=m.mean(axis=0);B=len(bands)
                        low=np.array([[mean[b,c,c].real for c in (0,1)] for b in range(B)])
                        rest=np.array([[sum(mean[b,2*g+c,2*h+c].real for g in range(1,6) for h in range(1,6)) for c in (0,1)] for b in range(B)])
                        cross=np.array([[2*sum(mean[b,c,2*h+c].real for h in range(1,6)) for c in (0,1)] for b in range(B)])
                        for f,value in (('low_power',low),('rest_power',rest),('signed_low_rest_cross',cross),('total_power',low+rest+cross)):
                            assert (abs(value-z[prefix+'_group_'+f])/ref[:,None]).max()<2e-9
                        r['band_Gram_matrices']+=len(m)*B
                    ref=max(float(abs(measured['time_energy_Gram']).max()),1e-24)
                    for k in ('all_frequency_Gram','time_energy_Gram'):assert abs(measured[k]-z[k]).max()/ref<2e-9
                    assert abs(measured['all_frequency_Gram'].real-measured['time_energy_Gram']).max()/ref<2e-9
                    nrmse=float(np.linalg.norm(z['audio']-audio)/np.linalg.norm(audio));assert abs(nrmse-float(z['wave_NRMSE']))<2e-12
                    objective,stationarity,bound=objective_gradient(z['nodes'],positions,scale,target,measured['coefficients'])
                    expected=case['solve']['objective'] if name=='inverse' else case['baseline_objective']
                    assert abs(objective-expected)<2e-8*max(1,expected),(label,name,objective,expected)
                    if name=='inverse':
                        assert abs(stationarity-case['solve']['relative_stationarity'])<2e-9
                        assert bool(case['solve']['stop'] in (1,2,4,5) and stationarity<2e-7)==case['solve']['converged']
                    verified['variants'][name]=dict(objective=objective,relative_stationarity=stationarity,conservative_ridge_solution_distance_bound=bound)
                r['captures']+=1;print('AUDITED source inverse',label,name,flush=True)
            r['cases'].append(verified);save(a.out/'report.json',r)
        producer=read();assert producer['result']=='observer_inverse_all6_measured'
        for path,digest in producer['inputs'].items():assert sha(path)==digest
        r.update(result='independent_observer_inverse_real_passed',all_converged=producer['all_converged'],producer_sha256=sha(a.study/'report.json'),
                 auditor_sha256=sha(__file__),oracles_sha256={n:sha(repo/n) for n in helpers},not_stochastic_source_or_timbre_qualification=True)
        assert r['captures']==12 and r['band_Gram_matrices']==5760
        save(a.out/'report.json',r);print(r['result'],'all_converged',r['all_converged'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise
    finally:
        if handle:kernel.CloseHandle(handle)


if __name__=='__main__':main()
