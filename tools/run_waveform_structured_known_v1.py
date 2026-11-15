"""Same original12 with node-axis roots, streamed columns and implicit Q."""
import argparse
import os
import shutil
import sys
import time
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','original','baseline','prerequisite','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--block',type=int,default=16)
    p.add_argument('--backend',choices=('structured','stream'),default='structured');a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_representer_v1.fixtures import DenseFixture
    from observer_complete_v1.synthesis import WaveSynthesis
    from observer_supported_v1.metric import SupportedMetric
    from observer_supported_v1.fit import SupportedSystem
    from observer_representer_v1.dual import representer_certificate
    from observer_representer_v1.primal import PenaltyPrimal
    from observer_frequency_v1.optimality import bound
    from observer_inverse_v1.fit import real_vector,complex_array
    from waveform_representer_v1.metric import supported_gram
    from waveform_structured_v1.penalty import TemporalPenalty
    from waveform_structured_v1.resources import ArrayLedger,process_memory
    from waveform_structured_v1.solver import solve
    if a.backend=='stream':from waveform_stream_v1.solver import solve
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',backend=a.backend,pid=os.getpid(),cases=[],sources={},inputs={},material_read=False,
        previous_goal_turn_classification='progress: frozen graph12/12 and precision diagnosis ate8c3825',block=a.block)
    try:
        required=load(a.prerequisite/'report.json')
        assert required['result']=='independent_waveform_structured_controls_passed' and required['all_qualified']
        baseline=load(a.baseline/'report.json');assert baseline['all_qualified']
        for path in (a.prerequisite/'report.json',a.baseline/'report.json'):r['inputs'][str(path)]=sha(path)
        parents={kind:(a.original/folder,load(a.original/folder/'report.json')) for kind,folder in
                 (('algebra','primal_algebra1'),('Hann','context1'))}
        names={n for _,parent in parents.values() for n in parent['sources']}
        names.update(p.relative_to(repo).as_posix() for p in (repo/'tools/waveform_structured_v1').glob('*.py'))
        if a.backend=='stream':
            names.update(p.relative_to(repo).as_posix() for p in (repo/'tools/waveform_stream_v1').glob('*.py'))
            names.add('research/waveform_structured_stream_v1_plan.json')
        names.update(('tools/run_waveform_structured_known_v1.py','tools/waveform_representer_v1/metric.py',
                      'research/waveform_graph_structured_v1_plan.json'))
        for name in sorted(names):
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        baseline_cases={(c['kind'],c['label']):c for c in baseline['cases']}
        def run_case(kind,folder,case):
            original=folder/case['file'];assert sha(original)==case['sha256'];r['inputs'][str(original)]=sha(original)
            bcase=baseline_cases[kind,case['label']];bpath=a.baseline/bcase['file']
            assert sha(bpath)==bcase['sha256'];r['inputs'][str(bpath)]=sha(bpath)
            started=time.perf_counter();cpu=time.process_time();ledger=ArrayLedger()
            with np.load(original) as old:
                if kind=='algebra':
                    system=DenseFixture(case['channels'],case['weak'],case['silent_right']);audio=system.audio
                    assert np.array_equal(system.A,old['A']) and np.array_equal(audio,old['audio'])
                    W=np.array(system.wave_metric,order='F');reference=old['original']
                    positions,orders=system.positions,system.orders
                    forward=lambda x:system.Phi@x
                    adjoint=lambda x:system.Phi.T@x
                else:
                    audio,positions,orders,scale=(old[n] for n in ('audio','positions','orders','scale'))
                    synthesis=WaveSynthesis(len(audio),positions,orders,1)
                    metric=SupportedMetric(audio,64.);system=SupportedSystem(synthesis,scale,metric)
                    print('BUILDING STRUCTURED',case['label'],len(audio),'PID',os.getpid(),flush=True)
                    W=supported_gram(metric,order='F')
                    reference=real_vector(old['original_dense_nodes']/scale[None])
                    forward=lambda x:synthesis.synthesize(complex_array(x,system.nshape)*system.scale[None]).ravel()
                    adjoint=lambda x:real_vector(synthesis.adjoint(x.reshape(audio.shape))*system.scale[None])
            prior=TemporalPenalty(system.nshape,system.D.toarray(),system.alpha,system.beta)
            rng=np.random.default_rng(361507)
            metric_probes=rng.normal(size=(len(W),4));metric_products=W@metric_probes
            node_probes=rng.normal(size=(system.nsize,3))
            root_maps={n:getattr(prior,n)(node_probes) for n in ('root','root_transpose','inverse','inverse_transpose','apply')}
            metric_seconds=time.perf_counter()-started
            values,info=solve(forward,adjoint,prior,W,audio.ravel(),ledger,block=a.block)
            root_seconds=time.perf_counter()-started-metric_seconds
            ledger.snapshot('caller.after_solver')
            q=values['q'];fitted=complex_array(q,system.nshape)*system.scale[None]
            residual=system@q-system.rhs(audio);u=-residual[:system.ysize]
            gradient=float(np.linalg.norm(system.rmatvec(residual))/np.linalg.norm(system.rmatvec(system.rhs(audio))))
            relative=float(np.linalg.norm(q-reference)/np.linalg.norm(reference))
            rc,pc=bound(system,audio,fitted),representer_certificate(system,audio,fitted,u)
            original_pass=bool(relative<2e-7 and gradient<2e-7 and rc['additional_gap_gate_passed'] and pc['additional_gap_gate_passed'])
            primal=PenaltyPrimal(system);assert np.array_equal(prior.L,primal.prior.L)
            original_z=prior.root_transpose(q)
            original_rhs=np.r_[system.rhs(audio)[:system.ysize],np.zeros(system.nsize)]
            original_direct=primal@original_z-original_rhs
            model_data=system.rhs(values['wave_model_residual'].reshape(audio.shape))[:system.ysize]
            original_model=np.r_[model_data,original_z];normal=primal.rmatvec(original_model)
            basis=np.zeros(system.nsize);squared=0.
            for j in range(system.nsize):
                basis[j]=1;col=primal@basis;squared+=float(col@col);basis[j]=0
            frobenius=np.sqrt(squared)
            stable_ratio=float(np.linalg.norm(normal)/max(frobenius*np.linalg.norm(original_model),1e-300))
            backward=float(np.linalg.norm(original_direct-original_model)/np.linalg.norm(original_rhs))
            info.update(original_stable_normal_relative=stable_ratio,original_backward_discrepancy=backward,
                original_stable_guard_passed=bool(stable_ratio<=1e-11 and backward<=1e-11))
            qualified=bool(original_pass and info['original_stable_guard_passed'] and info['stable_root_guard_passed'])
            with np.load(bpath) as old:
                baseline_error=float(np.linalg.norm(q-old['q'])/np.linalg.norm(old['q']))
            path=a.out/(kind+'_'+case['file'])
            ledger.snapshot('caller.before_serialization')
            np.savez_compressed(path,audio=audio,positions=positions,orders=orders,scale=system.scale,
                original=reference,node_probes=node_probes,metric_probes=metric_probes,metric_products=metric_products,
                original_model_residual=original_model,original_model_normal=normal,u=u,
                **{'node_'+n:v for n,v in root_maps.items()},**values)
            ledger.snapshot('caller.after_serialization')
            return dict(kind=kind,label=case['label'],file=path.name,sha256=sha(path),original_file=str(original),
                baseline_file=str(bpath),dense_relative_error=relative,baseline_graph_relative_error=baseline_error,
                original_gradient=gradient,residual_certificate=rc,representer_certificate=pc,
                original_equations_and_gap_passed=original_pass,qualified=qualified,solver=info,
                metric_build_seconds=metric_seconds,root_and_solve_seconds=root_seconds,
                elapsed_seconds=time.perf_counter()-started,cpu_seconds=time.process_time()-cpu,
                process_memory=process_memory(),resources=ledger.report(),
                allocation_scope='Solver has no packed denseR/fullQ/Phi; small algebra fixture itself retains original A/Phi/R oracle arrays')
        for kind,(folder,parent) in parents.items():
            r['inputs'][str(folder/'report.json')]=sha(folder/'report.json')
            for case in parent['cases']:
                row=run_case(kind,folder,case);r['cases'].append(row);save(a.out/'report.json',r)
                print(kind,case['label'],'original',row['original_equations_and_gap_passed'],'qualified',row['qualified'],
                    'normal',row['solver']['original_stable_normal_relative'],'peak',row['process_memory']['cumulative_peak_working_set_bytes'],flush=True)
        assert len(r['cases'])==12
        r.update(result='waveform_structured_original12_measured',all_qualified=all(c['qualified'] for c in r['cases']),
            all_original_equations_and_gaps_passed=all(c['original_equations_and_gap_passed'] for c in r['cases']),
            full_or_real_or_runtime_or_hearing_qualified=False)
        save(a.out/'report.json',r);print(r['result'],r['all_qualified'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
