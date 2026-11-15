"""Full independent waveform, moment, original observer and signed Gram audit."""
import argparse,json,os,shutil,sys,time
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','seam','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--follow-pid',type=int)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from quantile_surface_v1.audit_oracle import phase,midpoint_moments,generate
    from circular_phase_lift_v1.audit_oracle import fields,statistics,observe,group_summary
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    helpers=('tools/quantile_surface_v1/audit_oracle.py','tools/circular_phase_lift_v1/audit_oracle.py')
    for i,name in enumerate(helpers):shutil.copy2(repo/name,a.out/f'executed_oracle_{i}.py')
    r=dict(result='running',pid=os.getpid(),waves=0,observer_rows=0,Gram_matrices=0,midpoint_moments=0,cases=[],
           maximum_wave_error_FS=0.,maximum_phase_step_error=0.,maximum_moment_error=0.,maximum_observer_error_FS=0.,
           maximum_Gram_scaled_error=0.,maximum_statistics_scaled_error=0.)
    print('QUANTILE_SURFACE_AUDITOR_PID',os.getpid(),flush=True)
    kernel=None;handle=None
    try:
        if a.follow_pid and os.name=='nt':
            import ctypes
            from ctypes import wintypes
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.OpenProcess.argtypes=(wintypes.DWORD,wintypes.BOOL,wintypes.DWORD);kernel.OpenProcess.restype=wintypes.HANDLE
            kernel.GetExitCodeProcess.argtypes=(wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD));kernel.GetExitCodeProcess.restype=wintypes.BOOL
            kernel.CloseHandle.argtypes=(wintypes.HANDLE,);kernel.CloseHandle.restype=wintypes.BOOL
            handle=kernel.OpenProcess(0x1000,False,a.follow_pid)
        def alive():
            if not a.follow_pid:return False
            if os.name=='nt':
                if not handle:return False
                code=wintypes.DWORD()
                if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)):raise ctypes.WinError(ctypes.get_last_error())
                return code.value==259
            os.kill(a.follow_pid,0);return True
        def read():
            while True:
                try:return load(a.study/'report.json')
                except (FileNotFoundError,json.JSONDecodeError):
                    if not alive():raise
                    time.sleep(.2)
        # The NEW oracle must pass known phase/moment controls before sources.
        kd=load(a.seam/'report.json');assert kd['result']=='quantile_seam_known_ready'
        assert sha(a.seam/'seam.npz')==kd['file_sha256']
        with np.load(a.seam/'seam.npz') as z:known={k:z[k] for k in z.files}
        q=phase(known['product'],known['uniform'],known['knots'],known['cdf'],known['low'],known['high'])
        assert abs(q-known['phase']).max()<2e-12
        old,new=midpoint_moments(known['cdf'],known['low'],known['high'])
        assert abs(old[0]-known['conditional_moment'][16])<2e-12 and abs(new[0]-known['quantile_moment'][16])<2e-12
        r['known_before_sources']=True;r['known_seam_sha256']=sha(a.seam/'report.json')
        producer=read();assert producer['result'] in ('running','quantile_surface_all54_ready')
        if producer['result']=='running':assert a.follow_pid and producer['pid']==a.follow_pid and alive()
        for name,digest in producer['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
        plan=load(a.study/'exact_sources/research/quantile_surface_real_v1_plan.json');gate=plan['gates']
        parent=a.workspace/'baselines/conditional_phase_time_v1/evidence/real1'
        def check_stats(truth,saved,prefix,json_value=False):
            mean=truth['mean'];outer=np.maximum(np.outer(mean,mean),1e-48)
            scales=dict(mean=np.maximum(mean,1e-24),covariance=outer,lag_covariance=outer,
                mid_power=np.maximum((mean[::2]+mean[1::2])/2,1e-24),side_power=np.maximum((mean[::2]+mean[1::2])/2,1e-24))
            for k,x in truth.items():
                y=np.asarray(saved[prefix+k])
                if x.dtype.kind=='b':assert np.array_equal(x,y);continue
                if json_value and np.iscomplexobj(x):y=y[...,0]+1j*y[...,1]
                error=float((abs(x-y)/scales.get(k,1.)).max());assert error<gate['statistics_scaled'],(prefix,k,error)
                r['maximum_statistics_scaled_error']=max(r['maximum_statistics_scaled_error'],error)
        def cases():
            consumed=0
            while True:
                d=read();assert d['result'] in ('running','quantile_surface_all54_ready'),d.get('error')
                for name,digest in d['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
                for path,digest in d['inputs'].items():assert sha(path)==digest
                while consumed<len(d['cases']):
                    yield d['cases'][consumed];consumed+=1
                if d['result']=='quantile_surface_all54_ready':return
                if not alive():
                    final=read();assert final['result']=='quantile_surface_all54_ready','Producer terminal without a complete report; no restart.'
                    continue
                time.sleep(2)
        for row in cases():
            label,root=row['label'],row['root_hz']
            with np.load(parent/label/'bundle.npz') as z:bundle={k:z[k] for k in z.files}
            desc=row['midpoint_moments'];path=a.study/label/desc['file'];assert sha(path)==desc['sha256']
            with np.load(path) as saved:
                for name in plan['decoders']:
                    previous=[];candidate=[]
                    for j in range(len(bundle['mean_product'])):
                        c=bundle[name][j].copy();c[:,0]=0.;c[:,-1]=1.
                        old,new=midpoint_moments(c,bundle['low'][j],bundle['high'][j]);previous.append(old);candidate.append(new)
                        for value,key in ((old,name+'_old'),(new,name+'_new')):
                            error=float(abs(value-saved[key][j]).max());assert error<gate['circular_moment'],(label,name,j,error)
                            r['maximum_moment_error']=max(r['maximum_moment_error'],error)
                        r['midpoint_moments']+=len(old)
                    loss=abs(np.asarray(candidate)-np.asarray(previous));d=desc['summary'][name]
                    assert d['count']==loss.size and abs(d['mean_loss']-loss.mean())<2e-12 and abs(d['maximum_loss']-loss.max())<2e-12
            model={k[6:]:v for k,v in bundle.items() if k.startswith('model_')}
            for seed in row['seeds']:
                with np.load(parent/label/f'probe_{seed["seed"]}.npz') as z:capture={k:z[k] for k in ('state','independent_state')}
                amp,common,u=fields(model,capture,plan['frames'])
                for name,desc in seed['decoders'].items():
                    path=a.study/label/desc['file'];assert sha(path)==desc['sha256']
                    with np.load(path) as saved:
                        expected,maximum,rms,ip,ic=generate(bundle,amp,common,u,root,plan['carrier_edges_Hz'],plan['bands_Hz'],name)
                        error=float(abs(expected-saved['grouped_audio']).max());assert error<gate['independent_wave_FS'],(label,name,error)
                        r['maximum_wave_error_FS']=max(r['maximum_wave_error_FS'],error)
                        error=float(max(abs(maximum-saved['maximum_phase_step']).max(),abs(rms-saved['RMS_phase_step']).max()))
                        assert error<gate['phase_step_radians'];r['maximum_phase_step_error']=max(r['maximum_phase_step_error'],error)
                        check_stats(statistics(ip,ic),saved,'instant_')
                        measured=observe(saved['grouped_audio'],root,plan['bands_Hz'])
                        assert np.array_equal(saved['grouped_audio'].sum(axis=1),saved['audio'])
                        error=float(abs(measured['coefficients']-saved['coefficients']).max());assert error<gate['independent_wave_FS']
                        r['maximum_observer_error_FS']=max(r['maximum_observer_error_FS'],error)
                        for prefix,pk,ck in (('line','power','cross'),('broad','broadband_power','broadband_cross')):
                            power,cross=measured[pk],measured[ck];scale=np.maximum(power.reshape(241,4,2).mean(axis=(0,2)),1e-24)
                            assert (abs(power-saved[pk]).reshape(241,4,2)/scale[None,:,None]).max()<gate['statistics_scaled']
                            assert (abs(cross-saved[ck])/scale[None]).max()<gate['statistics_scaled']
                            truth=statistics(power,cross);check_stats(truth,saved,prefix+'_');check_stats(truth,desc['statistics'],prefix+'_',True)
                            m=measured[prefix+'_Gram'];gs=np.maximum(np.diagonal(m,axis1=-2,axis2=-1).real.sum(axis=-1).max(axis=0),1e-24)
                            error=float((abs(m-saved[prefix+'_Gram'])/gs[None,:,None,None]).max());assert error<gate['Gram_per_band_scaled']
                            r['maximum_Gram_scaled_error']=max(r['maximum_Gram_scaled_error'],error)
                            for key,value in group_summary(m).items():assert (abs(value-saved[prefix+'_'+key])/scale.reshape((4,)+(1,)*(value.ndim-1))).max()<gate['statistics_scaled']
                            width=row['source_rows'];chunks=[statistics(power[t:t+width],cross[t:t+width]) for t in range(0,len(power)-width+1,width)]
                            for field in ('mean','CV','complex_coherence'):assert abs(np.stack([c[field] for c in chunks])-saved['chunks_'+prefix+'_'+field]).max()<gate['statistics_scaled']
                            r['Gram_matrices']+=241*4
                        scale=max(float(np.diagonal(measured['time_energy_Gram'],axis1=-2,axis2=-1).sum(axis=-1).max()),1e-24)
                        for key in ('time_energy_Gram','all_frequency_Gram'):assert abs(measured[key]-saved[key]).max()/scale<gate['statistics_scaled']
                        assert abs(measured['all_frequency_Gram'].real-measured['time_energy_Gram']).max()/scale<gate['statistics_scaled']
                    r['waves']+=1;r['observer_rows']+=241;print('AUDITED Q surface',label,seed['seed'],name,flush=True)
                del amp,common,u
            r['cases'].append(dict(label=label,waves=9));save(a.out/'report.json',r)
        assert (r['waves'],r['observer_rows'],r['Gram_matrices'],r['midpoint_moments'])==(54,13014,104112,160704)
        final=read();assert final['result']=='quantile_surface_all54_ready'
        r.update(result='independent_quantile_surface_real_passed',producer_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__),
                 oracles_sha256={n:sha(repo/n) for n in helpers},native_or_C_or_listening=False)
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as e:r.update(result='failed',error=repr(e));save(a.out/'report.json',r);raise
    finally:
        if handle:kernel.CloseHandle(handle)


if __name__=='__main__':main()
