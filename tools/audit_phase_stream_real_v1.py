"""Full independent empirical inverse, scalar-partial wave, STFT and Gram audit."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from circular_phase_lift_v1.audit_oracle import fields,statistics,observe,group_summary
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    helper=repo/'tools/circular_phase_lift_v1/audit_oracle.py';shutil.copy2(helper,a.out/'executed_oracle.py')
    report=dict(result='running',waveforms=0,observer_rows=0,matrices=0,cases=[],
        maximum_full_group_wave_error_FS=0.,maximum_observer_error_FS=0.,
        maximum_Gram_per_band_scaled_error=0.,maximum_statistics_scaled_error=0.,maximum_phase_step_error=0.)
    try:
        producer=load(a.study/'report.json');assert producer['result']=='phase_stream_all18_ready'
        for name,digest in producer['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
        for path,digest in producer['inputs'].items():assert sha(path)==digest
        plan=load(a.study/'exact_sources/research/phase_stream_control_v1_plan.json');gate=plan['checks']
        parent=a.workspace/'baselines/conditional_phase_time_v1/evidence/real1'

        def check(actual,saved,prefix,json_encoded=False):
            mean=actual['mean'];outer=np.maximum(np.outer(mean,mean),1e-48)
            scales=dict(mean=np.maximum(mean,1e-24),covariance=outer,lag_covariance=outer,
                mid_power=np.maximum((mean[::2]+mean[1::2])/2,1e-24),side_power=np.maximum((mean[::2]+mean[1::2])/2,1e-24))
            for key,value in actual.items():
                target=np.asarray(saved[prefix+key])
                if value.dtype.kind=='b':assert np.array_equal(value,target);continue
                if json_encoded and np.iscomplexobj(value):target=target[...,0]+1j*target[...,1]
                error=float((abs(value-target)/scales.get(key,1.)).max());assert error<gate['statistics_scaled'],(prefix,key,error)
                report['maximum_statistics_scaled_error']=max(report['maximum_statistics_scaled_error'],error)

        for row in producer['cases']:
            label,root=row['label'],row['root_hz']
            with np.load(parent/label/'bundle.npz') as z:model={key[6:]:z[key] for key in z.files if key.startswith('model_')}
            h=len(model['fixed_phase']);n=np.arange(plan['frames'])
            tags=np.searchsorted(plan['carrier_edges_Hz'],np.arange(1,h+1)*root,side='right')-1
            x=np.clip((np.arange(1,h+1)*root-19200)/2400,0,1);taper=1-3*x*x+2*x*x*x
            count=len(model['phase']);nodes=np.r_[0.,(np.arange(count)+.5)/count,1.]
            for seed in row['seeds']:
                with np.load(parent/label/f'probe_{seed["seed"]}.npz') as z:
                    capture={key:z[key] for key in ('state','independent_state','probe_positions','probe_amplitude','probe_common',
                        'relative_maximum_unwrapped_relative_phase_step')}
                amplitude,common,uniform=fields(model,capture,plan['frames'])
                path=a.study/label/seed['file'];assert sha(path)==seed['sha256']
                with np.load(path) as saved:
                    grouped=saved['grouped_audio'];expected=np.zeros_like(grouped)
                    assert np.array_equal(grouped.sum(axis=1),saved['audio'])
                    probes=capture['probe_positions']
                    assert abs(amplitude[probes]-saved['probe_amplitude']).max()<2e-12
                    assert abs(common[probes]-saved['probe_common']).max()<2e-12
                    for j in range(h):
                        delta=np.interp(uniform[:,j],nodes,np.r_[model['phase'][0,h+j],model['phase'][:,h+j],model['phase'][-1,h+j]])
                        assert abs(delta[probes]-saved['probe_relative'][:,j]).max()<2e-12
                        step=abs(np.diff(delta)).max();error=abs(step-saved['independent_relative_max_step'][j])
                        assert error<2e-10;report['maximum_phase_step_error']=max(report['maximum_phase_step_error'],float(error))
                        for c,sign in ((0,1),(1,-1)):
                            angle=2*np.pi*(n%1024)/1024*(j+1)+common[:,j]+sign*delta/2
                            expected[:,tags[j],c]+=amplitude[:,j,c]*taper[j]*np.cos(angle)
                    assert abs(capture['relative_maximum_unwrapped_relative_phase_step']-saved['original_relative_max_step']).max()<2e-10
                    error=float(abs(expected-grouped).max());assert error<gate['independent_wave_FS'],error
                    report['maximum_full_group_wave_error_FS']=max(report['maximum_full_group_wave_error_FS'],error)
                    observed=observe(grouped,root,plan['bands_Hz'])
                    error=float(abs(observed['coefficients']-saved['coefficients']).max());assert error<gate['independent_wave_FS']
                    report['maximum_observer_error_FS']=max(report['maximum_observer_error_FS'],error)
                    for prefix,pk,ck in (('line','power','cross'),('broad','broadband_power','broadband_cross')):
                        matrix=observed[prefix+'_Gram']
                        scale=np.maximum(np.diagonal(matrix,axis1=-2,axis2=-1).real.sum(axis=-1).max(axis=0),1e-24)
                        error=float((abs(matrix-saved[prefix+'_Gram'])/scale[None,:,None,None]).max())
                        assert error<gate['Gram_per_band_scaled'];report['maximum_Gram_per_band_scaled_error']=max(report['maximum_Gram_per_band_scaled_error'],error)
                        power,cross=observed[pk],observed[ck]
                        band_scale=np.maximum(power.reshape(241,4,2).mean(axis=(0,2)),1e-24)
                        assert (abs(power-saved[pk]).reshape(241,4,2)/band_scale[None,:,None]).max()<gate['statistics_scaled']
                        assert (abs(cross-saved[ck])/band_scale[None]).max()<gate['statistics_scaled']
                        stats=statistics(power,cross);check(stats,saved,prefix+'_');check(stats,seed['statistics'],prefix+'_',True)
                        for key,value in group_summary(matrix).items():
                            assert (abs(value-saved[prefix+'_group_'+key])/band_scale.reshape((4,)+(1,)*(value.ndim-1))).max()<gate['statistics_scaled']
                        width=row['source_rows']
                        chunks=[statistics(power[t:t+width],cross[t:t+width]) for t in range(0,len(power)-width+1,width)]
                        for field in ('mean','CV','complex_coherence'):
                            assert abs(np.stack([s[field] for s in chunks])-saved['chunks_'+prefix+'_'+field]).max()<gate['statistics_scaled']
                        report['matrices']+=241*4
                    global_scale=max(float(np.diagonal(observed['time_energy_Gram'],axis1=-2,axis2=-1).sum(axis=-1).max()),1e-24)
                    for key in ('all_frequency_Gram','time_energy_Gram'):assert abs(observed[key]-saved[key]).max()/global_scale<gate['statistics_scaled']
                    assert abs(observed['all_frequency_Gram'].real-observed['time_energy_Gram']).max()/global_scale<gate['statistics_scaled']
                    report['waveforms']+=1;report['observer_rows']+=241
                print('AUDITED independent stream full waveform',label,seed['seed'],flush=True)
                del amplitude,common,uniform,expected,observed
            report['cases'].append(dict(label=label,waveforms=len(row['seeds'])));save(a.out/'report.json',report)
        assert (report['waveforms'],report['observer_rows'],report['matrices'])==(18,4338,34704)
        report.update(result='independent_phase_stream_real_passed',producer_sha256=sha(a.study/'report.json'),
            auditor_sha256=sha(__file__),oracle_sha256=sha(helper),normalized_coordinate_only=True,heard=False)
        save(a.out/'report.json',report);print(report['result'],flush=True)
    except BaseException as e:
        report.update(result='failed',error=repr(e));save(a.out/'report.json',report);raise


if __name__=='__main__':main()
