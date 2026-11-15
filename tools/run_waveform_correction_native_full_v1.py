"""One preflight-gated full known band/native correction with true phase release."""
import argparse
import os
import shutil
import sys
import time
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','original','prerequisite','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_complete_v1.synthesis import WaveSynthesis
    from observer_supported_v1.metric import SupportedMetric
    from observer_supported_v1.fit import SupportedSystem
    from observer_representer_v1.primal import PenaltyPrimal
    from observer_representer_v1.dual import representer_certificate
    from observer_frequency_v1.optimality import bound
    from observer_inverse_v1.fit import complex_array
    from waveform_stream_v1.shared import SharedSupportedGeometry
    from waveform_banded_v1.metric import supported_banded
    from waveform_correction_v1.pipeline import solve_corrected
    from waveform_correction_v1.trace import original_frobenius
    from waveform_structured_v1.penalty import TemporalPenalty
    from waveform_structured_v1.resources import ArrayLedger,process_memory
    from run_waveform_stream_full_v1 import physical_memory
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic()
    r=dict(result='running',pid=os.getpid(),sources={},inputs={},material_read=False,only_one_attempt=True)
    class Telemetry(ArrayLedger):
        def add(self,name,value):
            result=super().add(name,value)
            if name.startswith('source_block.') and int(name.split('.')[-1])%2048==0:
                self.snapshot('building_columns_'+name.split('.')[-1])
            return result
        def snapshot(self,phase):
            super().snapshot(phase)
            entry=dict(pid=os.getpid(),status='running',phase=phase,elapsed_seconds=time.monotonic()-started,
                **process_memory(),**physical_memory())
            save(a.out/'progress.json',entry)
            print('NATIVE_FULL',phase,round(entry['elapsed_seconds'],2),'WS',entry['working_set_bytes'],
                  'FREE',entry['available_physical_bytes'],flush=True)
            if entry['available_physical_bytes']<1024**3:
                raise MemoryError('Available physical memory below declared1GiB checkpoint guard')
    try:
        prerequisite=load(a.prerequisite/'storage_audit2/report.json')
        assert prerequisite['result']=='independent_waveform_correction_storage_verified'
        assert prerequisite['both_native_and_pipeline_same_as_previous'] and prerequisite['all_actual_phase_releases_verified']
        assert prerequisite['production_trace_controls']==13
        for prefix,digest in prerequisite['producer_bindings'].items():
            assert sha(a.prerequisite/(prefix+'1')/'report.json')==digest
        checked_kernel=load(a.prerequisite/'pipeline_shared1/report.json')['sources']
        for leaf in ('inverse.py','native_inverse.py','native_triangular.py','correct.py','pipeline.py'):
            name='tools/waveform_correction_v1/'+leaf
            assert sha(repo/name)==checked_kernel[name]
        assert sha(repo/'tools/waveform_correction_v1/trace.py')==prerequisite['trace_source_sha256']
        for n in ('controls_audit1','known_audit1','shared_audit1','pipeline_known_audit1','pipeline_shared_audit1'):
            path=a.prerequisite/n/'report.json';v=load(path);assert v['all_qualified'];r['inputs'][str(path)]=sha(path)
        original=load(a.original/'report.json')
        root=a.workspace/'baselines/waveform_stream_full_v1'
        assert a.original.is_relative_to(root)
        assert sha(root/'manifest.json')==load(repo/'research/waveform_stream_full_v1_summary.json')['manifest_sha256']
        r['inputs'][str(root/'manifest.json')]=sha(root/'manifest.json')
        assert original['result']=='waveform_stream_full_known_measured' and original['solver_qualified'] and original['fidelity_qualified']
        assert sha(a.original/'capture.npz')==original['capture_sha256']
        for path in (a.original/'report.json',a.original/'capture.npz',a.prerequisite/'storage_audit2/report.json'):
            r['inputs'][str(path)]=sha(path)
        names=set(original['sources'])
        for folder in ('waveform_correction_v1','waveform_banded_v1','waveform_stream_v1','waveform_structured_v1',
                       'observer_supported_v1','observer_complete_v1','observer_representer_v1'):
            names.update(path.relative_to(repo).as_posix() for path in (repo/'tools'/folder).glob('*.py'))
        names.update(('tools/run_waveform_correction_native_full_v1.py','tools/run_waveform_stream_full_v1.py',
            'research/waveform_correction_native_full_v1_plan.json'))
        for name in sorted(names):
            path=a.out/'exact_sources'/name;path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,path);r['sources'][name]=sha(path)
        with np.load(a.original/'capture.npz') as z:
            capture={n:z[n] for n in ('audio','positions','orders','scale','nodes','factors','loadings')}
        audio,positions,orders,scale=(capture[n] for n in ('audio','positions','orders','scale'))
        assert audio.shape==(12289,2) and len(positions)==49 and len(orders)==288
        memory=physical_memory();main=8368514064;reserve=3*1024**3//2;headroom=3*1024**3
        required=main+reserve+headroom
        r['resource_preflight']=dict(**memory,main_phase_arrays=main,native_temporary_allowance=reserve,
            headroom_guard=headroom,required_available=required,
            passed=min(memory['available_physical_bytes'],memory['available_commit_bytes'])>=required,
            NOT_actual_peak_proof=True)
        save(a.out/'report.json',r)
        if not r['resource_preflight']['passed']:raise MemoryError('Full native preflight failed; no large allocation')
        synthesis=WaveSynthesis(len(audio),positions,orders,2)
        metric=SupportedMetric(audio,64.);system=SupportedSystem(synthesis,scale,metric)
        shared=SharedSupportedGeometry(system);ledger=Telemetry()
        metric_action=lambda e:e/metric.wave_scale**2+metric.adjoint(metric.forward(e))
        values,inverse,pipeline,initial=solve_corrected(shared.forward,shared.adjoint,shared.prior,
            lambda:supported_banded(metric),audio,metric_action,ledger,128)
        q=shared.interleave(values['q']);fitted=complex_array(q,system.nshape)*system.scale[None]
        wave=synthesis.synthesize(fitted);residual=system@q-system.rhs(audio);u=-residual[:system.ysize]
        gradient=float(np.linalg.norm(system.rmatvec(residual))/np.linalg.norm(system.rmatvec(system.rhs(audio))))
        rc,pc=bound(system,audio,fitted),representer_certificate(system,audio,fitted,u)
        primal=PenaltyPrimal(system)
        z=TemporalPenalty(system.nshape,system.D.toarray(),system.alpha,system.beta).root_transpose(q)
        rhs=np.r_[system.rhs(audio)[:system.ysize],np.zeros(system.nsize)]
        model=np.r_[system.rhs(values['wave_model_residual'])[:system.ysize],z]
        normal=primal.rmatvec(model)
        trace=original_frobenius(positions,orders,scale,metric,shared.prior.L,2);normA=trace['root_Frobenius']
        stable=float(np.linalg.norm(normal)/(normA*np.linalg.norm(model)))
        backward=float(np.linalg.norm(primal@z-rhs-model)/np.linalg.norm(rhs))
        error=wave-audio;rows,ref=metric.forward(error),metric.forward(audio)
        starts=metric.frame.starts[metric.keep];central=(starts>=2048)&(starts+4096<=10241)
        metrics=dict(whole_wave_NRMSE=float(np.linalg.norm(error)/np.linalg.norm(audio)),
            target_wave_NRMSE=float(np.linalg.norm(error[2048:10241])/np.linalg.norm(audio[2048:10241])),
            target_supported_band_complex_NRMSE=[float(np.linalg.norm(rows[central][:,metric.bands==b])/np.linalg.norm(ref[central][:,metric.bands==b])) for b in range(6)],
            whole_supported_band_complex_NRMSE=[float(np.linalg.norm(rows[:,metric.bands==b])/np.linalg.norm(ref[:,metric.bands==b])) for b in range(6)],
            whole_wave_regions_NRMSE=[float(np.linalg.norm(error[s])/np.linalg.norm(audio[s])) for s in (slice(0,2048),slice(2048,10241),slice(10241,None))])
        qualified=bool(gradient<2e-7 and stable<=1e-11 and backward<=1e-11
            and pipeline['base_solver']['stable_root_guard_passed']
            and rc['additional_gap_gate_passed'] and pc['additional_gap_gate_passed'])
        capture.update(values,fitted=fitted,wave=wave,u=u,weights=metric.weights,band_power=metric.band_power,
            floor_active=metric.floor_active,original_model_residual=model,original_model_normal=normal,
            **{'base_'+n:v for n,v in initial.items()})
        ledger.snapshot('native_full.before_small_capture')
        np.savez_compressed(a.out/'capture.npz',**capture)
        ledger.snapshot('native_full.saved')
        comparisons=[]
        for name,val in metrics.items():
            now=val if isinstance(val,list) else [val]
            old=original['metrics'][name];old=old if isinstance(old,list) else [old]
            comparisons.extend(dict(metric=name,index=i,previous=x,current=y,regressed=y>x) for i,(x,y) in enumerate(zip(old,now)))
        assert len(comparisons)==17
        r.update(result='waveform_correction_native_full_known_measured',solver=pipeline['base_solver'],
            pipeline=pipeline,inverse_info=inverse.info(),production_original_trace=trace,
            original_gradient=gradient,original_stable_complete_normal=stable,original_backward_discrepancy=backward,
            residual_certificate=rc,representer_certificate=pc,metrics=metrics,solver_qualified=qualified,
            fidelity_qualified=bool(metrics['target_wave_NRMSE']<.02 and max(metrics['target_supported_band_complex_NRMSE'])<.02),
            comparison_rows=comparisons,capture_sha256=sha(a.out/'capture.npz'),resources=ledger.report(),
            process_memory=process_memory(),solve_wall_seconds=time.monotonic()-started,
            original_reference_metrics=original['metrics'],large_QR_arrays_NOT_serialized=True,
            no_parameter_error_to_unknown_dense_optimum_claim=True,independently_qualified=False,
            source_or_runtime_or_hearing_qualified=False)
        save(a.out/'report.json',r)
        print(r['result'],'solver',qualified,'fidelity',r['fidelity_qualified'],flush=True)
        print('COMPLETE',gradient,stable,backward,'GAPS',rc['gap_upper_bound'],pc['gap_upper_bound'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error),process_memory=process_memory())
        save(a.out/'report.json',r);raise


if __name__=='__main__':main()
