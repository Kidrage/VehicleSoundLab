"""Run the same frozen four algebra and eight original-Hann cases, without material."""
import argparse, ctypes, os, shutil, sys, time
from pathlib import Path
from research_archive_v1 import load, save, sha


def peak_working_set():
    class Counters(ctypes.Structure):
        _fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong)]+[(n,ctypes.c_size_t) for n in
            ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage',
             'QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    api=ctypes.WinDLL('psapi',use_last_error=True).GetProcessMemoryInfo
    api.argtypes=(ctypes.c_void_p,ctypes.POINTER(Counters),ctypes.c_ulong)
    values=Counters();values.cb=ctypes.sizeof(values)
    assert api(kernel.GetCurrentProcess(),ctypes.byref(values),values.cb)
    return values.PeakWorkingSetSize


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','original','prerequisite','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_representer_v1.fixtures import DenseFixture
    from observer_complete_v1.synthesis import WaveSynthesis
    from observer_supported_v1.metric import SupportedMetric
    from observer_supported_v1.fit import SupportedSystem
    from observer_representer_v1.dual import representer_certificate
    from observer_representer_v1.primal import PenaltyPrimal
    from observer_frequency_v1.optimality import bound
    from observer_inverse_v1.fit import real_vector,complex_array
    from waveform_representer_v1.metric import supported_gram
    from waveform_representer_v1.algebra import solve
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',pid=os.getpid(),cases=[],sources={},inputs={},material_read=False,
        previous_goal_turn_classification='progress: one terminal full288 failure independently diagnosed and archived at4e85935')
    try:
        prerequisite=load(a.prerequisite/'report.json')
        assert prerequisite['result']=='independent_waveform_representer_explicit_passed' and prerequisite['all_qualified']
        r['inputs'][str(a.prerequisite/'report.json')]=sha(a.prerequisite/'report.json')
        parents={kind:(a.original/folder,load(a.original/folder/'report.json')) for kind,folder in
                 (('algebra','primal_algebra1'),('Hann','context1'))}
        names={n for _,parent in parents.values() for n in parent['sources']}
        names.update(('tools/run_waveform_representer_known_v1.py','tools/waveform_representer_v1/metric.py',
            'tools/waveform_representer_v1/algebra.py','research/observer_stable_full_followup_v1_plan.json'))
        for name in sorted(names):
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        for kind,(folder,parent) in parents.items():
            r['inputs'][str(folder/'report.json')]=sha(folder/'report.json')
            for case in parent['cases']:
                original=folder/case['file'];assert sha(original)==case['sha256']
                r['inputs'][str(original)]=sha(original)
                started=time.monotonic()
                with np.load(original) as old:
                    if kind=='algebra':
                        system=DenseFixture(case['channels'],case['weak'],case['silent_right'])
                        audio=system.audio
                        assert np.array_equal(system.A,old['A']) and np.array_equal(audio,old['audio'])
                        Phi,W,R=system.Phi,system.wave_metric,system.R
                        reference=old['original']
                        positions,orders=system.positions,system.orders
                    else:
                        audio,positions,orders,scale=(old[n] for n in ('audio','positions','orders','scale'))
                        synthesis=WaveSynthesis(len(audio),positions,orders,1)
                        metric=SupportedMetric(audio,64.)
                        system=SupportedSystem(synthesis,scale,metric)
                        Phi=np.column_stack([synthesis.synthesize(complex_array(column,system.nshape)*scale[None]).ravel()
                                             for column in np.eye(system.nsize)])
                        D=system.D.toarray();K=.001*D.T@D+.000001*np.eye(len(positions))
                        R=linalg.block_diag(np.kron(K,np.eye(len(orders))),np.kron(K,np.eye(len(orders))))
                        print('BUILDING METRIC',case['label'],len(audio),'PID',os.getpid(),flush=True)
                        W=supported_gram(metric)
                        reference=real_vector(old['original_dense_nodes']/scale[None])
                metric_seconds=time.monotonic()-started
                values,info=solve(Phi,W,R,audio.ravel())
                solve_seconds=time.monotonic()-started-metric_seconds
                q=values['q'];fitted=complex_array(q,system.nshape)*system.scale[None]
                residual=system@q-system.rhs(audio)
                u=-residual[:system.ysize]
                gradient=float(np.linalg.norm(system.rmatvec(residual))/np.linalg.norm(system.rmatvec(system.rhs(audio))))
                relative=float(np.linalg.norm(q-reference)/np.linalg.norm(reference))
                rc,pc=bound(system,audio,fitted),representer_certificate(system,audio,fitted,u)
                original_pass=bool(relative<2e-7 and gradient<2e-7 and rc['additional_gap_gate_passed'] and pc['additional_gap_gate_passed'])
                primal=PenaltyPrimal(system)
                normalized=complex_array(q,system.nshape)
                original_z=real_vector((primal.prior.L.T@normalized.reshape(len(normalized),-1)).reshape(system.nshape))
                original_rhs=np.r_[system.rhs(audio)[:system.ysize],np.zeros(system.nsize)]
                original_direct=primal@original_z-original_rhs
                model_data=system.rhs(values['wave_model_residual'].reshape(audio.shape))[:system.ysize]
                original_model=np.r_[model_data,original_z]
                original_model_normal=primal.rmatvec(original_model)
                frobenius=np.sqrt(sum(float(np.sum((primal@column)**2)) for column in np.eye(system.nsize)))
                stable_ratio=float(np.linalg.norm(original_model_normal)/max(frobenius*np.linalg.norm(original_model),1e-300))
                backward=float(np.linalg.norm(original_direct-original_model)/np.linalg.norm(original_rhs))
                info.update(original_stable_normal_relative=stable_ratio,original_backward_discrepancy=backward,
                    original_stable_guard_passed=bool(stable_ratio<=1e-11 and backward<=1e-11))
                qualified=bool(original_pass and info['original_stable_guard_passed'] and info['stable_root_guard_passed'])
                rng=np.random.default_rng(758934)
                probes=rng.normal(size=(len(W),4))
                products=W@probes
                # Keep only the applied root/features, not eight dense8705^2
                # roots. Independent original all-column equations audit their
                # exact source-visible quadratic/linear/constant terms.
                path=a.out/(kind+'_'+case['file'])
                np.savez_compressed(path,Phi=Phi,R=R,audio=audio,positions=positions,orders=orders,
                    scale=system.scale,original=reference,u=u,metric_probes=probes,metric_products=products,
                    original_model_residual=original_model,original_model_normal=original_model_normal,**values)
                row=dict(kind=kind,label=case['label'],file=path.name,sha256=sha(path),original_file=str(original),
                    solver=info,dense_relative_error=relative,original_gradient=gradient,
                    residual_certificate=rc,representer_certificate=pc,original_equations_and_gap_passed=original_pass,
                    qualified=qualified,metric_build_seconds=metric_seconds,root_and_solve_seconds=solve_seconds,
                    dense_wave_metric_bytes=W.nbytes,process_peak_working_set_bytes=peak_working_set())
                r['cases'].append(row);save(a.out/'report.json',r)
                print(kind,case['label'],'original',original_pass,'strict',qualified,'error',relative,
                    'directnormal',info['original_direct_whitened_normal_relative'],'seconds',metric_seconds+solve_seconds,flush=True)
                del W,values,Phi,R,probes,products
        assert len(r['cases'])==12
        r.update(result='waveform_representer_original12_measured',
            all_original_equations_and_gaps_passed=all(c['original_equations_and_gap_passed'] for c in r['cases']),
            all_qualified=all(c['qualified'] for c in r['cases']),
            real_or_full_or_runtime_or_hearing_qualified=False)
        save(a.out/'report.json',r);print(r['result'],r['all_qualified'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
