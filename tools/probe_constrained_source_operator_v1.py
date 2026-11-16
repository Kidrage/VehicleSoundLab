"""Execute complete known operators, never source fitting or vehicle file loading."""
import argparse
import os
from pathlib import Path
import shutil
import sys
import time
from research_archive_v1 import save,sha


SOURCES=('tools/constrained_source_operator_v1/__init__.py','tools/constrained_source_operator_v1/source.py',
    'tools/constrained_source_operator_v1/observation.py','tools/constrained_source_operator_v1/prior.py',
    'tools/constrained_source_operator_v1/system.py','tools/constrained_source_operator_v1/fixtures.py',
    'tools/probe_constrained_source_operator_v1.py','tools/audit_constrained_source_operator_v1.py',
    'tools/constrained_source_operator_v1/oracle.py','tools/observer_complete_v1/synthesis.py',
    'tools/observer_forward_v1/polyphase.py','tools/observer_forward_v1/operator.py',
    'tools/c1_declared_objective_v1/profile.py','tools/locked_source_guard_v1/measurement.py',
    'tools/observer_complete_v1/audit_oracle.py','tools/waveform_structured_v1/resources.py',
    'research/constrained_source_operator_v1_plan.json','tools/research_archive_v1.py')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from constrained_source_operator_v1.fixtures import definitions,nodes
    from constrained_source_operator_v1.system import System
    from c1_declared_objective_v1.profile import calibrate
    from waveform_structured_v1.resources import process_memory
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',sources={},cases=[],no_vehicle_inputs=True)
    try:
        for name in SOURCES:
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        rng=np.random.default_rng(2026111601)
        for name,frames,positions,orders in definitions():
            started=time.perf_counter();scale=(.1/orders**.7)[:,None];scale[orders>180]*=.01
            # Initial uncalibrated source constructs a deterministic known wave.
            from constrained_source_operator_v1.source import Source
            source=Source(frames,positions,orders,scale)
            x=source.vector(nodes(name,positions,orders));wave=source.forward(x)
            n=np.arange(frames);perturbation=np.column_stack((np.cos(2*np.pi*211*n/1024),.4*np.sin(2*np.pi*193*n/1024)))*2e-6
            if name=='small_silent_right':perturbation[:,1]=0
            if name=='small_zero':perturbation[:]=0
            audio=wave+perturbation;old=calibrate(audio[2048:-2048])
            system=System(frames,positions,orders,scale,old['weights'],old['amplitude'],old['sigma'])
            full=system.full_forward(x);target=system.target_forward(x)
            full_dual=rng.standard_normal(len(full));target_dual=tuple(rng.standard_normal(v.shape) for v in target)
            wave_dual=rng.standard_normal(wave.shape)
            t0=time.perf_counter();full_adj=system.full_adjoint(full_dual);full_adjoint_seconds=time.perf_counter()-t0
            t0=time.perf_counter();target_adj=system.target_adjoint(target_dual);target_adjoint_seconds=time.perf_counter()-t0
            source_adj=system.source.adjoint(wave_dual);prior=system.prior.apply(x);inverse=system.prior.inverse(x)
            # These dot products do not replace the independent audit.
            dot_full=float(abs(full@full_dual-x@full_adj)/max(np.linalg.norm(full)*np.linalg.norm(full_dual),1e-300))
            dot_target=float(abs(sum(v@y for v,y in zip(target,target_dual))-x@target_adj)/max(np.linalg.norm(x)*np.linalg.norm(target_adj),1e-300))
            assert max(dot_full,dot_target)<2e-11
            packet=dict(frames=np.array(frames),positions=positions,orders=orders,scale=scale,
                weights=old['weights'],amplitude=np.array(old['amplitude']),sigma=np.array(old['sigma']),
                x=x,wave=wave,audio=audio,full_forward=full,full_dual=full_dual,full_adjoint=full_adj,
                target_adjoint=target_adj,wave_dual=wave_dual,source_adjoint=source_adj,
                prior_apply=prior,prior_inverse=inverse,gradient=system.gradient(x,audio))
            for g,(value,dual) in enumerate(zip(target,target_dual)):packet['target_'+str(g)]=value;packet['target_dual_'+str(g)]=dual
            null_norm=None
            if name=='small_rank_deficient':
                null=np.zeros(system.size);null[system.source.half]=1.
                packet['null_vector']=null;packet['null_wave']=system.source.forward(null)
                null_norm=float(np.linalg.norm(packet['null_wave']));assert null_norm==0.
            report=dict(name=name,frames=frames,nodes=len(positions),orders=len(orders),unknowns=system.size,
                full_data_rows=len(full),target_group_rows=[len(v) for v in target],
                whole_supported_windows=len(system.observation.starts),target_supported_windows=len(system.observation.target_slots),
                objective=system.objective(x,audio),assessment=system.assess(wave,audio),
                dot_full_scaled_error=dot_full,dot_target_scaled_error=dot_target,exact_null_wave_norm=null_norm,
                full_adjoint_seconds=full_adjoint_seconds,target_adjoint_seconds=target_adjoint_seconds,
                known_operator_elapsed_seconds=time.perf_counter()-started,process_memory=process_memory(),
                full_real_matrix_estimated_bytes=len(full)*system.size*8,
                no_dense_full_matrix_or_actual_factors_allocated=True)
            directory=a.out/name;directory.mkdir();np.savez_compressed(directory/'operators.npz',**packet)
            report['packet_sha256']=sha(directory/'operators.npz');save(directory/'report.json',report)
            r['cases'].append(report);save(a.out/'report.json',r)
            print('KNOWN_OPERATOR',name,system.size,len(full),max(dot_full,dot_target),flush=True)
        r.update(result='complete_known_matrixfree_source_operators_executed',verification_requires_independent_audit=True,
            constrained_solver_not_implemented_or_qualified=True,new_C1_source_eligible_for_statistics=False,
            no_vehicle_fit_native_rate_audio_C_or_naturalness_qualification=True)
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
