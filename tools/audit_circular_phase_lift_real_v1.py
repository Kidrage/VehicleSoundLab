"""Independent frozen inputs/quantiles/unwrap/full OSC/SciPy Gram audit."""
import argparse
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        os.environ[name]='2'
    sys.path.insert(0,str(args.workspace/'tools/python_deps'))
    import numpy as np
    from circular_phase_lift_v1.audit_oracle import fields,phase,statistics,observe,group_summary
    repo=Path(__file__).resolve().parents[1]
    args.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,args.out/'executed_audit.py')
    helper=args.out/'executed_audit_oracle.py'
    shutil.copy2(repo/'tools/circular_phase_lift_v1/audit_oracle.py',helper)
    report=dict(result='running',cases=[],waveforms=0,matrices=0,observer_rows=0,
        maximum_full_group_wave_error_FS=0.,maximum_original_probe_error_FS=0.,
        maximum_old_phase_step_error=0.,maximum_Gram_per_band_scaled_error=0.,
        maximum_statistics_scaled_error=0.,maximum_observer_error_FS=0.,
        maximum_circular_error=0.,maximum_gauge_probe_error_FS=0.,
        no_crossing_grouped_waves_bit_exact=0)
    try:
        producer=load(args.study/'report.json')
        assert producer['result']=='all90_frozen_phase_lift_candidates_ready'
        for name,digest in producer['sources'].items():
            assert sha(repo/name)==sha(args.study/'exact_sources'/name)==digest
        for path,digest in producer['inputs'].items():
            assert sha(path)==digest
        plan=load(args.study/'exact_sources/research/circular_phase_lift_real_v1_plan.json')
        gate=plan['checks']
        parent=args.workspace/'baselines/conditional_phase_time_v1/evidence/real1'
        carrier=args.workspace/'baselines/carrier_transfer_v1'
        carrier_report=load(carrier/'evidence/real1/report.json')
        descriptors={(row['label'],seed['seed'],name):value for row in carrier_report['cases'] for seed in row['seeds'] for name,value in seed['variants'].items()}
        carrier_entries={v['path']:v['sha256'] for v in load(carrier/'manifest.json')['files']}

        def check_stats(actual,saved,prefix,json_encoded=False):
            mean=actual['mean']
            scales=dict(mean=np.maximum(mean,1e-24),covariance=np.maximum(np.outer(mean,mean),1e-48),
                lag_covariance=np.maximum(np.outer(mean,mean),1e-48),
                mid_power=np.maximum((mean[::2]+mean[1::2])/2,1e-24),side_power=np.maximum((mean[::2]+mean[1::2])/2,1e-24))
            for key,value in actual.items():
                target=np.asarray(saved[prefix+key])
                if value.dtype.kind=='b':
                    assert np.array_equal(value,target)
                    continue
                if json_encoded and np.iscomplexobj(value):
                    target=target[...,0]+1j*target[...,1]
                error=float((abs(value-target)/scales.get(key,1.)).max())
                assert error<gate['statistics_scaled'],(prefix,key,error)
                report['maximum_statistics_scaled_error']=max(report['maximum_statistics_scaled_error'],error)

        for row in producer['cases']:
            label,root=row['label'],row['root_hz']
            with np.load(parent/label/'bundle.npz') as raw:
                bundle={name:raw[name] for name in raw.files}
            model={name[6:]:v for name,v in bundle.items() if name.startswith('model_')}
            h=len(model['fixed_phase'])
            tags=np.searchsorted(plan['carrier_edges_Hz'],np.arange(1,h+1)*root,side='right')-1
            x=np.clip((np.arange(1,h+1)*root-19200)/2400,0,1)
            taper=1-3*x*x+2*x*x*x
            for seed in row['seeds']:
                with np.load(parent/label/f'probe_{seed["seed"]}.npz') as raw:
                    capture={name:raw[name] for name in ('state','independent_state','probe_positions','probe_amplitude','probe_common')}
                    for name in plan['variants']:
                        capture[name+'_audio']=raw[name+'_audio']
                        if name!='fixed':
                            capture[name+'_maximum_unwrapped_relative_phase_step']=raw[name+'_maximum_unwrapped_relative_phase_step']
                frames=len(capture['fixed_audio'])
                n=np.arange(frames)
                probes=capture['probe_positions']
                amplitude,common,uniform=fields(model,capture,frames)
                assert abs(amplitude[probes]-capture['probe_amplitude']).max()<2e-12
                assert abs(common[probes]-capture['probe_common']).max()<2e-12
                for name,desc in seed['variants'].items():
                    path=args.study/label/desc['file']
                    assert sha(path)==desc['sha256']
                    with np.load(path) as saved:
                        grouped=saved['grouped_audio']
                        assert np.array_equal(grouped.sum(axis=1),saved['audio'])
                        if name in ('fixed','relative'):
                            original=descriptors[label,seed['seed'],name]
                            old_path=carrier/'evidence/real1'/label/original['file']
                            assert sha(old_path)==original['sha256']==carrier_entries[old_path.relative_to(carrier).as_posix()]
                            with np.load(old_path) as old:
                                assert np.array_equal(grouped,old['grouped_audio'])
                            report['no_crossing_grouped_waves_bit_exact']+=1
                            if name=='relative':
                                assert not saved['lift_branch_counts'].any() and not saved['lift_terminal_winding'].any()
                        else:
                            expected=np.zeros_like(grouped)
                            raw_probes=np.zeros((len(probes),2))
                            gauge_probes=np.zeros_like(raw_probes)
                            for j in range(h):
                                product=amplitude[:,j,0]*amplitude[:,j,1]/bundle['mean_product'][j]
                                delta=phase(product,uniform[:,j],bundle['knots'][j],bundle[name][j],bundle['low'][j],bundle['high'][j])
                                lifted=np.unwrap(delta)
                                winding=np.rint((delta-lifted)/(2*np.pi)).astype(np.int64)
                                increments=np.diff(np.r_[0,winding])
                                assert np.count_nonzero(increments)==saved['lift_branch_counts'][j]
                                assert np.count_nonzero(winding)==saved['lift_changed_samples'][j]
                                assert winding[-1]==saved['lift_terminal_winding'][j]
                                assert np.array_equal(winding[probes],saved['lift_probe_winding'][:,j])
                                step_error=abs(abs(np.diff(delta)).max()-capture[name+'_maximum_unwrapped_relative_phase_step'][j])
                                assert step_error<gate['independent_phase_radians']
                                assert abs(abs(np.diff(delta)).max()-saved['lift_maximum_raw_step'][j])<gate['independent_phase_radians']
                                report['maximum_old_phase_step_error']=max(report['maximum_old_phase_step_error'],float(step_error))
                                assert abs(abs(np.diff(lifted)).max()-saved['lift_maximum_lifted_step'][j])<gate['independent_phase_radians']
                                margin=np.pi-abs(np.angle(np.exp(1j*np.diff(delta))))
                                assert abs(margin.min()-saved['lift_minimum_half_turn_margin'][j])<gate['independent_phase_radians']
                                # Real half-turn ambiguity is retained and would
                                # need explicit qualification before this audit.
                                assert saved['lift_ambiguous_steps'][j]==0
                                assert margin.min()>32*np.finfo(float).eps*np.pi
                                circular=float(abs(np.exp(1j*lifted)-np.exp(1j*delta)).max())
                                assert circular<gate['circular_invariant']
                                report['maximum_circular_error']=max(report['maximum_circular_error'],circular)
                                carrier_phase=2*np.pi*(n%1024)/1024*(j+1)
                                for channel,sign in [(0,1),(1,-1)]:
                                    expected[:,tags[j],channel]+=amplitude[:,j,channel]*taper[j]*np.cos(carrier_phase+common[:,j]+sign*lifted/2)
                                    for k,sample in enumerate(probes):
                                        raw_probes[k,channel]+=amplitude[sample,j,channel]*taper[j]*math.cos(float(carrier_phase[sample])+float(common[sample,j])+sign*float(delta[sample])/2)
                                        compensated_common=common[sample,j]+math.pi*winding[sample]
                                        gauge_probes[k,channel]+=amplitude[sample,j,channel]*taper[j]*math.cos(float(carrier_phase[sample])+float(compensated_common)+sign*float(lifted[sample])/2)
                            error=float(abs(expected-grouped).max())
                            assert error<gate['independent_wave_FS'],(label,seed['seed'],name,error)
                            report['maximum_full_group_wave_error_FS']=max(report['maximum_full_group_wave_error_FS'],error)
                            error=float(abs(raw_probes-capture[name+'_audio'][probes]).max())
                            assert error<gate['independent_wave_FS']
                            report['maximum_original_probe_error_FS']=max(report['maximum_original_probe_error_FS'],error)
                            error=float(abs(raw_probes-gauge_probes).max())
                            assert error<gate['independent_wave_FS']
                            report['maximum_gauge_probe_error_FS']=max(report['maximum_gauge_probe_error_FS'],error)
                        observed=observe(grouped,root,plan['bands_Hz'])
                        error=float(abs(observed['coefficients']-saved['coefficients']).max())
                        assert error<gate['independent_wave_FS']
                        report['maximum_observer_error_FS']=max(report['maximum_observer_error_FS'],error)
                        for prefix,power_key,cross_key in [('line','power','cross'),('broad','broadband_power','broadband_cross')]:
                            matrix=observed[prefix+'_Gram']
                            scales=np.maximum(np.diagonal(matrix,axis1=-2,axis2=-1).real.sum(axis=-1).max(axis=0),1e-24)
                            error=float((abs(matrix-saved[prefix+'_Gram'])/scales[None,:,None,None]).max())
                            assert error<gate['Gram_per_band_scaled']
                            report['maximum_Gram_per_band_scaled_error']=max(report['maximum_Gram_per_band_scaled_error'],error)
                            report['matrices']+=int(np.prod(matrix.shape[:2]))
                            power,cross=observed[power_key],observed[cross_key]
                            band_scale=np.maximum(power.reshape(241,4,2).mean(axis=(0,2)),1e-24)
                            assert (abs(power-saved[power_key]).reshape(241,4,2)/band_scale[None,:,None]).max()<gate['statistics_scaled']
                            assert (abs(cross-saved[cross_key])/band_scale[None]).max()<gate['statistics_scaled']
                            value=statistics(power,cross)
                            check_stats(value,saved,prefix+'_')
                            check_stats(value,desc['statistics'],prefix+'_',True)
                            for field,part in group_summary(matrix).items():
                                target=saved[prefix+'_group_'+field]
                                scale=band_scale.reshape((4,)+(1,)*(part.ndim-1))
                                assert (abs(part-target)/scale).max()<gate['statistics_scaled']
                            count=row['source_rows']
                            chunks=[statistics(power[start:start+count],cross[start:start+count]) for start in range(0,len(power)-count+1,count)]
                            for field in ('mean','CV','complex_coherence'):
                                assert abs(np.stack([c[field] for c in chunks])-saved['chunks_'+prefix+'_'+field]).max()<gate['statistics_scaled']
                        global_scale=max(float(np.diagonal(observed['time_energy_Gram'],axis1=-2,axis2=-1).sum(axis=-1).max()),1e-24)
                        for field in ('all_frequency_Gram','time_energy_Gram'):
                            assert abs(observed[field]-saved[field]).max()/global_scale<gate['statistics_scaled']
                        assert abs(observed['all_frequency_Gram'].real-observed['time_energy_Gram']).max()/global_scale<gate['statistics_scaled']
                        report['waveforms']+=1
                        report['observer_rows']+=len(observed['power'])
                del amplitude,common,uniform
                print('AUDITED lift/full OSC/original observer',label,seed['seed'],flush=True)
            report['cases'].append(dict(label=label,seeds=len(row['seeds']),waveforms=15))
            save(args.out/'report.json',report)
        assert report['waveforms']==90 and report['matrices']==173520
        report.update(result='independent_circular_phase_lift_real_passed',producer_sha256=sha(args.study/'report.json'),
            auditor_sha256=sha(__file__),oracle_sha256=sha(helper),normalized_coordinate_only=True,heard=False)
        save(args.out/'report.json',report)
        print(report['result'],flush=True)
    except BaseException as error:
        report.update(result='failed',error=repr(error))
        save(args.out/'report.json',report)
        raise


if __name__=='__main__':
    main()
