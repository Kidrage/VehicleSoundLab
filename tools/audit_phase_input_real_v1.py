"""Independent all-sample conditional inverses, four waves, terms and observer."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import time
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--follow-pid',type=int,help='Follow a specifically verified live producer; audit only completed case checkpoints.')
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from circular_phase_lift_v1.audit_oracle import fields,phase,statistics
    from phase_input_paths_v1.audit_oracle import observe,budget
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    helpers=('tools/circular_phase_lift_v1/audit_oracle.py','tools/phase_input_paths_v1/audit_oracle.py')
    for i,name in enumerate(helpers):shutil.copy2(repo/name,a.out/f'executed_oracle_{i}.py')
    report=dict(result='running',sets=0,counterfactuals=0,observer_rows=0,term_matrices=0,cases=[],
        maximum_full_group_wave_error_FS=0.,maximum_wave_term_error_FS=0.,maximum_phase_step_error=0.,
        maximum_phase_interaction_error=0.,maximum_observer_error_FS=0.,maximum_Gram_scaled_error=0.,maximum_statistics_scaled_error=0.)
    try:
        def producer_alive():
            if os.name!='nt':
                os.kill(a.follow_pid,0)
                return True
            # Windows signal 0 is a console-control value, not a read-only
            # POSIX liveness probe. Query the process exit code explicitly.
            import ctypes
            from ctypes import wintypes
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.OpenProcess.argtypes=(wintypes.DWORD,wintypes.BOOL,wintypes.DWORD)
            kernel.OpenProcess.restype=wintypes.HANDLE
            kernel.GetExitCodeProcess.argtypes=(wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD))
            kernel.GetExitCodeProcess.restype=wintypes.BOOL
            kernel.CloseHandle.argtypes=(wintypes.HANDLE,)
            kernel.CloseHandle.restype=wintypes.BOOL
            handle=kernel.OpenProcess(0x1000,False,a.follow_pid)
            if not handle:return False
            try:
                code=wintypes.DWORD()
                if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)):raise ctypes.WinError(ctypes.get_last_error())
                return code.value==259
            finally:kernel.CloseHandle(handle)
        def read_producer():
            while True:
                try:return load(a.study/'report.json')
                except (FileNotFoundError,json.JSONDecodeError):
                    if not a.follow_pid:raise
                    assert producer_alive(),'Confirmed producer handle is no longer live; no restart performed.'
                    time.sleep(.2)
        producer=read_producer();assert producer['result'] in ('running','phase_input_all54_sets_ready')
        if not a.follow_pid:assert producer['result']=='phase_input_all54_sets_ready'
        for name,digest in producer['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
        for path,digest in producer['inputs'].items():assert sha(path)==digest
        plan=load(a.study/'exact_sources/research/phase_input_paths_v1_plan.json');gate=plan['checks']
        parent=a.workspace/'baselines/conditional_phase_time_v1/evidence/real1'
        def check_stats(value,saved,prefix,json_encoded=False):
            mean=value['mean'];outer=np.maximum(np.outer(mean,mean),1e-48)
            scales=dict(mean=np.maximum(mean,1e-24),covariance=outer,lag_covariance=outer,
                mid_power=np.maximum((mean[::2]+mean[1::2])/2,1e-24),side_power=np.maximum((mean[::2]+mean[1::2])/2,1e-24))
            for key,x in value.items():
                y=np.asarray(saved[prefix+key])
                if x.dtype.kind=='b':assert np.array_equal(x,y);continue
                if json_encoded and np.iscomplexobj(x):y=y[...,0]+1j*y[...,1]
                error=float((abs(x-y)/scales.get(key,1.)).max());assert error<gate['statistics_scaled'],(prefix,key,error)
                report['maximum_statistics_scaled_error']=max(report['maximum_statistics_scaled_error'],error)
        def completed_cases():
            consumed=0
            while True:
                checkpoint=read_producer();assert checkpoint['result'] in ('running','phase_input_all54_sets_ready'),checkpoint.get('error')
                if len(checkpoint['cases'])>consumed:
                    for name,digest in checkpoint['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
                    for path,digest in checkpoint['inputs'].items():assert sha(path)==digest
                    while consumed<len(checkpoint['cases']):
                        yield checkpoint['cases'][consumed]
                        consumed+=1
                if checkpoint['result']=='phase_input_all54_sets_ready':return
                assert a.follow_pid,'Producer is not finished; explicit live PID required.'
                assert producer_alive(),'Confirmed producer handle is no longer live; no restart performed.'
                time.sleep(2)
        for row in completed_cases():
            label,root=row['label'],row['root_hz']
            with np.load(parent/label/'bundle.npz') as z:bundle={k:z[k] for k in z.files}
            model={k[6:]:v for k,v in bundle.items() if k.startswith('model_')};h=len(model['fixed_phase'])
            n=np.arange(plan['frames']);orders=np.arange(1,h+1)
            tags=np.searchsorted(plan['carrier_edges_Hz'],orders*root,side='right')-1
            x=np.clip((orders*root-19200)/2400,0,1);taper=1-3*x*x+2*x*x*x
            for seed in row['seeds']:
                with np.load(parent/label/f'probe_{seed["seed"]}.npz') as z:capture={k:z[k] for k in ('state','independent_state')}
                amplitude,common,uniform=fields(model,capture,plan['frames'])
                for name,desc in seed['decoders'].items():
                    path=a.study/label/desc['file'];assert sha(path)==desc['sha256']
                    with np.load(path) as saved:
                        expected=np.zeros_like(saved['grouped_counterfactual_audio'])
                        for j in range(h):
                            product=amplitude[:,j,0]*amplitude[:,j,1]/bundle['mean_product'][j]
                            p0=np.ones(len(n));u0=np.full(len(n),.5)
                            delta=np.column_stack([phase(p,u,bundle['knots'][j],bundle[name][j],bundle['low'][j],bundle['high'][j]) for p,u in ((p0,u0),(product,u0),(p0,uniform[:,j]),(product,uniform[:,j]))])
                            error=float(abs(abs(np.diff(delta,axis=0)).max(axis=0)-saved['maximum_phase_step'][j]).max())
                            assert error<gate['phase_step_radians'];report['maximum_phase_step_error']=max(report['maximum_phase_step_error'],error)
                            phi=delta[:,3]-delta[:,1]-delta[:,2]+delta[:,0]
                            v=np.array([np.sqrt(np.mean(phi*phi)),abs(phi).max()])
                            error=float(abs(v-saved['phase_interaction_RMS_max'][j]).max());assert error<gate['phase_step_radians']
                            report['maximum_phase_interaction_error']=max(report['maximum_phase_interaction_error'],error)
                            for k in range(4):
                                for c,sign in ((0,1),(1,-1)):
                                    angle=2*np.pi*(n%1024)/1024*(j+1)+common[:,j]+sign*delta[:,k]/2
                                    expected[:,k,tags[j],c]+=amplitude[:,j,c]*taper[j]*np.cos(angle)
                        error=float(abs(expected-saved['grouped_counterfactual_audio']).max());assert error<gate['independent_wave_FS'],error
                        report['maximum_full_group_wave_error_FS']=max(report['maximum_full_group_wave_error_FS'],error)
                        counter=saved['grouped_counterfactual_audio'].sum(axis=2)
                        assert np.array_equal(counter,saved['counterfactual_audio'])
                        b,p,u,joint=np.moveaxis(counter,1,0)
                        terms=np.stack([b,p-b,u-b,joint-p-u+b],axis=1)
                        assert np.array_equal(terms,saved['term_audio'])
                        error=float(abs(terms.sum(axis=1)-joint).max());assert error<gate['wave_identity_FS']
                        report['maximum_wave_term_error_FS']=max(report['maximum_wave_term_error_FS'],error)
                        for k,tag in enumerate(plan['counterfactuals']):
                            observed=observe(counter[:,k,None,:],root,plan['bands_Hz'])
                            error=float(abs(observed['coefficients']-saved[tag+'_coefficients']).max());assert error<gate['independent_wave_FS']
                            report['maximum_observer_error_FS']=max(report['maximum_observer_error_FS'],error)
                            for prefix,pk,ck in (('line','power','cross'),('broad','broadband_power','broadband_cross')):
                                power,cross=observed[pk],observed[ck];scale=np.maximum(power.reshape(241,4,2).mean(axis=(0,2)),1e-24)
                                assert (abs(power-saved[tag+'_'+pk]).reshape(241,4,2)/scale[None,:,None]).max()<gate['statistics_scaled']
                                assert (abs(cross-saved[tag+'_'+ck])/scale[None]).max()<gate['statistics_scaled']
                                stats=statistics(power,cross);check_stats(stats,saved,tag+'_'+prefix+'_');check_stats(stats,desc['statistics'][tag],prefix+'_',True)
                                width=row['source_rows'];chunks=[statistics(power[t:t+width],cross[t:t+width]) for t in range(0,len(power)-width+1,width)]
                                for field in ('mean','CV','complex_coherence'):assert abs(np.stack([c[field] for c in chunks])-saved[tag+'_chunks_'+prefix+'_'+field]).max()<gate['statistics_scaled']
                            report['counterfactuals']+=1;report['observer_rows']+=241
                        measured=observe(terms,root,plan['bands_Hz'])
                        for prefix in ('line','broad'):
                            m=measured[prefix+'_Gram'];scale=np.maximum(np.diagonal(m,axis1=-2,axis2=-1).real.sum(axis=-1).max(axis=0),1e-24)
                            error=float((abs(m-saved['term_'+prefix+'_Gram'])/scale[None,:,None,None]).max());assert error<gate['Gram_per_band_scaled']
                            report['maximum_Gram_scaled_error']=max(report['maximum_Gram_scaled_error'],error)
                            values=budget(m);power=measured['power' if prefix=='line' else 'broadband_power']
                            bandscale=np.maximum(power.reshape(241,4,2).mean(axis=(0,2)),1e-24)
                            for key,value in values.items():assert (abs(value-saved['term_'+prefix+'_'+key])/bandscale.reshape((4,)+(1,)*(value.ndim-1))).max()<gate['statistics_scaled']
                            assert (abs(values['self_power'].sum(axis=1)+values['signed_pairs'].sum(axis=1)-values['total_power'])/bandscale[:,None]).max()<gate['statistics_scaled']
                            assert (abs(power-saved['joint_'+('power' if prefix=='line' else 'broadband_power')]).reshape(241,4,2)/bandscale[None,:,None]).max()<gate['statistics_scaled']
                            report['term_matrices']+=241*4
                        scale=max(float(np.diagonal(measured['time_energy_Gram'],axis1=-2,axis2=-1).sum(axis=-1).max()),1e-24)
                        for key in ('all_frequency_Gram','time_energy_Gram'):assert abs(measured[key]-saved['term_'+key]).max()/scale<gate['statistics_scaled']
                        assert abs(measured['all_frequency_Gram'].real-measured['time_energy_Gram']).max()/scale<gate['statistics_scaled']
                    report['sets']+=1;print('AUDITED all input paths',label,seed['seed'],name,flush=True)
                del amplitude,common,uniform
            report['cases'].append(dict(label=label,sets=9));save(a.out/'report.json',report)
        assert (report['sets'],report['counterfactuals'],report['observer_rows'],report['term_matrices'])==(54,216,52056,104112)
        producer=read_producer();assert producer['result']=='phase_input_all54_sets_ready'
        for path,digest in producer['inputs'].items():assert sha(path)==digest
        report.update(result='independent_phase_input_real_passed',producer_sha256=sha(a.study/'report.json'),
            auditor_sha256=sha(__file__),oracles_sha256={name:sha(repo/name) for name in helpers},normalized_coordinate_only=True,heard=False)
        save(a.out/'report.json',report);print(report['result'],flush=True)
    except BaseException as e:
        report.update(result='failed',error=repr(e));save(a.out/'report.json',report);raise


if __name__=='__main__':main()
