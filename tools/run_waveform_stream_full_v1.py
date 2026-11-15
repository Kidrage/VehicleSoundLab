"""One resource-gated exact graph solve of the frozen full stereo known problem."""
import argparse
import ctypes
import os
import shutil
import sys
import time
from pathlib import Path
from research_archive_v1 import load, save, sha


def physical_memory():
    class Status(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_ulonglong) for n in
            ('total','available','total_commit','available_commit','total_virtual','available_virtual','available_extended')]
    value=Status();value.length=ctypes.sizeof(value)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):raise ctypes.WinError()
    return dict(total_physical_bytes=value.total,available_physical_bytes=value.available,
        total_commit_bytes=value.total_commit,available_commit_bytes=value.available_commit)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','original','prerequisite','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
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
    from waveform_stream_v1.solver import solve
    from waveform_structured_v1.penalty import TemporalPenalty
    from waveform_structured_v1.resources import ArrayLedger,process_memory
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
            print('FULL',phase,round(entry['elapsed_seconds'],2),'WS',entry['working_set_bytes'],
                'FREE',entry['available_physical_bytes'],flush=True)
            if entry['available_physical_bytes']<1024**3:
                raise MemoryError('Available physical memory fell below declared1GiB checkpoint guard')
    try:
        prior=load(repo/'research/waveform_stream_v1_summary.json')
        assert prior['manifest_sha256']==sha(a.prerequisite/'manifest.json')
        assert prior['original12_qualified']==12 and prior['shared_interleaved_known_qualified']==8
        for receipt in prior['external_verification_receipts'].values():
            assert sha(receipt['path'])==receipt['sha256']
        original=load(a.original/'report.json')
        assert original['result']=='observer_representer_full_known_measured' and not original['solver_qualified']
        assert sha(a.original/'capture.npz')==original['capture_sha256']
        for path in (a.original/'report.json',a.original/'capture.npz',a.prerequisite/'manifest.json',
                     repo/'research/waveform_stream_v1_summary.json'):
            r['inputs'][str(path)]=sha(path)
        names=set(original['sources'])
        for folder in ('waveform_stream_v1','waveform_structured_v1','observer_supported_v1','observer_complete_v1',
                       'observer_forward_v1','observer_representer_v1'):
            names.update(f.relative_to(repo).as_posix() for f in (repo/'tools'/folder).glob('*.py'))
        names.update(('tools/run_waveform_stream_full_v1.py','tools/waveform_representer_v1/metric.py',
                      'research/waveform_stream_full_v1_plan.json'))
        for name in sorted(names):
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        with np.load(a.original/'capture.npz') as old:
            capture={name:old[name] for name in ('audio','positions','orders','scale','nodes','factors','loadings')}
        audio,positions,orders,scale=(capture[n] for n in ('audio','positions','orders','scale'))
        assert audio.shape==(12289,2) and len(positions)==49 and len(orders)==288
        memory=physical_memory();main_bytes=9173984280;allowance=3*1024**3//2;guard=3*1024**3
        minimum=main_bytes+allowance+guard
        r['resource_preflight']=dict(**memory,registered_four_array_bytes=main_bytes,
            unregistered_native_temporary_allowance=allowance,headroom_guard=guard,
            required_available_bytes=minimum,passed=bool(min(memory['available_physical_bytes'],memory['available_commit_bytes'])>=minimum),
            allowance_NOT_native_peak_proof=True)
        save(a.out/'report.json',r)
        if not r['resource_preflight']['passed']:raise MemoryError('Full known preflight headroom gate failed; no large allocation')
        print('FULL_STREAM_PID',os.getpid(),'PREFLIGHT',r['resource_preflight'],flush=True)
        synthesis=WaveSynthesis(len(audio),positions,orders,2)
        metric=SupportedMetric(audio,64.);system=SupportedSystem(synthesis,scale,metric)
        shared=SharedSupportedGeometry(system);ledger=Telemetry()
        ledger.snapshot('full.before_metric')
        W=shared.metric_matrix();ledger.add('full.metric_input',W);ledger.snapshot('full.metric_built')
        values,info=solve(shared.forward,shared.adjoint,shared.prior,W,audio,ledger,block=128)
        ledger.snapshot('full.after_solver')
        q=shared.interleave(values['q']);fitted=complex_array(q,system.nshape)*system.scale[None]
        wave=synthesis.synthesize(fitted);residual=system@q-system.rhs(audio);u=-residual[:system.ysize]
        gradient=float(np.linalg.norm(system.rmatvec(residual))/np.linalg.norm(system.rmatvec(system.rhs(audio))))
        rc,pc=bound(system,audio,fitted),representer_certificate(system,audio,fitted,u)
        primal=PenaltyPrimal(system)
        z=TemporalPenalty(system.nshape,system.D.toarray(),system.alpha,system.beta).root_transpose(q)
        rhs=np.r_[system.rhs(audio)[:system.ysize],np.zeros(system.nsize)]
        model=np.r_[system.rhs(values['wave_model_residual'])[:system.ysize],z]
        normal=primal.rmatvec(model)
        normA=np.sqrt(2)*info['augmented_root_Frobenius']
        stable=float(np.linalg.norm(normal)/(normA*np.linalg.norm(model)))
        backward=float(np.linalg.norm(primal@z-rhs-model)/np.linalg.norm(rhs))
        errors=wave-audio;rows,ref=metric.forward(errors),metric.forward(audio)
        starts=metric.frame.starts[metric.keep];central=(starts>=2048)&(starts+4096<=10241)
        metrics=dict(whole_wave_NRMSE=float(np.linalg.norm(errors)/np.linalg.norm(audio)),
            target_wave_NRMSE=float(np.linalg.norm(errors[2048:10241])/np.linalg.norm(audio[2048:10241])),
            target_supported_band_complex_NRMSE=[float(np.linalg.norm(rows[central][:,metric.bands==b])/np.linalg.norm(ref[central][:,metric.bands==b])) for b in range(6)],
            whole_supported_band_complex_NRMSE=[float(np.linalg.norm(rows[:,metric.bands==b])/np.linalg.norm(ref[:,metric.bands==b])) for b in range(6)],
            whole_wave_regions_NRMSE=[float(np.linalg.norm(errors[s])/np.linalg.norm(audio[s])) for s in (slice(0,2048),slice(2048,10241),slice(10241,None))])
        qualified=bool(gradient<2e-7 and stable<=1e-11 and backward<=1e-11 and info['stable_root_guard_passed']
            and rc['additional_gap_gate_passed'] and pc['additional_gap_gate_passed'])
        small={name:values[name] for name in ('q','z','t','transformed_target','graph_coordinates',
            'reduced_model_residual','root_model_residual','wave_model_residual','direct_transformed_normal','stable_root_normal','temporal_K','temporal_L')}
        capture.update(small,fitted=fitted,wave=wave,u=u,weights=metric.weights,band_power=metric.band_power,
            floor_active=metric.floor_active,original_model_residual=model,original_model_normal=normal)
        ledger.snapshot('full.before_small_capture')
        np.savez_compressed(a.out/'capture.npz',**capture)
        ledger.snapshot('full.saved')
        r.update(result='waveform_stream_full_known_measured',solver=info,original_gradient=gradient,
            original_stable_complete_normal=stable,original_backward_discrepancy=backward,
            residual_certificate=rc,representer_certificate=pc,metrics=metrics,solver_qualified=qualified,
            fidelity_qualified=bool(metrics['target_wave_NRMSE']<.02 and max(metrics['target_supported_band_complex_NRMSE'])<.02),
            capture_sha256=sha(a.out/'capture.npz'),resources=ledger.report(),process_memory=process_memory(),
            solve_wall_seconds=time.monotonic()-started,original_reference_metrics=original['metrics'],
            large_QR_arrays_NOT_serialized=True,no_parameter_error_to_unknown_dense_optimum_claim=True,
            independently_qualified=False,source_or_runtime_or_hearing_qualified=False)
        save(a.out/'report.json',r);print(r['result'],'solver',qualified,'fidelity',r['fidelity_qualified'],flush=True)
        print('ORIGINAL',gradient,stable,backward,'GAPS',rc['gap_upper_bound'],pc['gap_upper_bound'],'METRICS',metrics,flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error),process_memory=process_memory())
        save(a.out/'report.json',r);raise


if __name__=='__main__':main()
