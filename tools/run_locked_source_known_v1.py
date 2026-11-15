"""Known controls for explicit original-target plus context adapter, no materials."""
import argparse
import gc
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from locked_source_fit_v1.fixtures import cases
    from locked_source_fit_v1.adapter import build
    from waveform_file_real_v1.evaluate import evaluate
    from waveform_file_real_v1.resources import preflight
    from waveform_file_full_v1.pipeline import solve_full
    from waveform_file_full_v1.resources import Telemetry
    from waveform_banded_v1.metric import supported_banded
    from waveform_structured_v1.resources import process_memory
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',pid=os.getpid(),cases=[],sources={},inputs={},block=64,material_read=False)
    try:
        previous=load(a.workspace/'references/analysis/waveform_file_full_v1/full1/report.json')
        names=set(previous['sources'])
        names.update(p.relative_to(repo).as_posix() for p in (repo/'tools/waveform_file_real_v1').glob('*.py'))
        names.update(('tools/run_waveform_file_real_adapter_v1.py','tools/audit_waveform_file_real_adapter_v1.py',
            'research/waveform_file_real_adapter_v1_plan.json','tools/waveform_trace_audit_v1.py'))
        names.update(p.relative_to(repo).as_posix() for p in (repo/'tools/locked_source_fit_v1').glob('*.py'))
        names.update(('tools/run_locked_source_known_v1.py','tools/audit_locked_source_known_v1.py',
            'tools/waveform_real_guard_v1/locked.py','research/locked_source_fit_v1_plan.json'))
        for name in sorted(names):
            path=a.out/'exact_sources'/name
            path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,path)
            r['sources'][name]=sha(path)
        for z in cases():
            label=z['label'];directory=a.out/label;directory.mkdir()
            audio=z['audio']
            system,shared,reference=build(audio,z['target'],z['metric_target'],z['original_positions'],z['orders'],z['scale'])
            assert np.array_equal(system.synthesis.positions,z['positions'])
            rng=np.random.default_rng(94115)
            q=rng.normal(0,.2,system.nsize)
            rhsprobe=rng.normal(0,.1,system.shape[0])
            m=system.metric
            z.update(probe_q=q,probe_rows=rhsprobe,probe_forward=system@q,probe_adjoint=system.rmatvec(rhsprobe),
                probe_rhs=system.rhs(audio),weights=m.weights,band_power=m.band_power,floor_active=m.floor_active,
                time_coverage=m.time_coverage,coverage=m.frame.coverage,target_slots=m.target_window_slots,
                sigma=np.array(m.wave_scale),amplitude=np.array(m.amplitude_scale))
            if label=='both_zero':
                values=dict(q=np.zeros((shared.prior.size,2)),wave_model_residual=np.zeros_like(audio))
                outputs,stats=evaluate(system,shared,audio,values,dict(stable_root_guard_passed=True),reference)
                bad=dict(q=np.ones((shared.prior.size,2))*.01,wave_model_residual=np.ones_like(audio)*.01)
                _,badstats=evaluate(system,shared,audio,bad,dict(stable_root_guard_passed=True),reference)
                assert badstats['metrics']['target_wave_NRMSE'] is None and not badstats['fidelity_qualified']
                info=dict(zero_reference_bad_candidate=badstats,**stats)
                z.update(values,**outputs)
            else:
                ledger=Telemetry(directory)
                resource=preflight(directory,len(audio),len(z['positions']),len(z['orders']),64)
                assert resource['memory_passed'] and resource['disk_passed']
                factors=directory/'factors';factors.mkdir()
                action=lambda e:e/m.wave_scale**2+m.adjoint(m.forward(e))
                values,inverse,pipeline,initial,taus=solve_full(shared,lambda:supported_banded(m),audio,action,factors,ledger,64)
                inverse.close()
                inverse_info=inverse.info()
                outputs,stats=evaluate(system,shared,audio,values,pipeline['base_solver'],reference)
                z.update(values,**outputs,**taus,inverse_right_tau=inverse.right.tau,inverse_inner_tau=inverse.inner.tau,
                    **{'base_'+name:value for name,value in initial.items()})
                info=dict(**stats,pipeline=pipeline,solver=pipeline['base_solver'],inverse_info=inverse_info,
                    resource_preflight=resource,resources=ledger.report(),process_memory=process_memory(),no_full_factor_arrays_in_capture=True)
                if label=='silent_right':
                    assert np.count_nonzero(z['q'][:,1])==0 and np.count_nonzero(z['wave'][:,1])==0
                del inverse
            np.savez_compressed(directory/'capture.npz',**z)
            info.update(result='locked_source_fit_case_measured',label=label,file=label+'/capture.npz',capture_sha256=sha(directory/'capture.npz'),
                frames=len(audio),nodes=len(z['positions']),orders=len(z['orders']),block=64)
            save(directory/'report.json',info)
            r['cases'].append(dict(label=label,file=label+'/capture.npz',report=label+'/report.json',
                report_sha256=sha(directory/'report.json'),capture_sha256=info['capture_sha256'],
                solver_qualified=stats['solver_qualified'],fidelity_qualified=stats['fidelity_qualified']))
            save(a.out/'report.json',r)
            print('LOCKED_SOURCE_KNOWN',label,stats['solver_qualified'],stats['fidelity_qualified'],flush=True)
            del z,system,shared,reference,values,outputs,info
            gc.collect()
        invalid=[]
        sample=next(cases())
        for name,kw in (
            ('missing_metric_target',dict(metric_target=None)),
            ('short_metric_target',dict(metric_target=sample['metric_target'][:-1])),
            ('nonfinite_metric_target',dict(metric_target=sample['metric_target']*float('nan'))),
            ('changed_target_slice',dict(target=sample['target']*.99)),
            ('complex_audio',dict(audio=sample['audio'].astype(complex))),
            ('nonpositive_scale',dict(scale=-sample['scale']))):
            args={k:sample[k] for k in ('audio','target','metric_target','orders','scale')}
            args['positions']=sample['original_positions'];args.update(kw)
            try:build(**args)
            except (ValueError,TypeError):invalid.append(name)
            else:raise AssertionError('Invalid adapter input accepted: '+name)
        r['invalid_rejections']=invalid
        r.update(result='locked_source_fit_known_measured',all_qualified=all(c['solver_qualified'] and c['fidelity_qualified'] for c in r['cases']),
            process_memory=process_memory(),no_real_fit_or_C_or_listening_change=True)
        save(a.out/'report.json',r)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
