"""Execute distinct shared-column method on complete saved small known controls."""
import argparse
import os
from pathlib import Path
import shutil
import sys
import time
from research_archive_v1 import load,save,sha


SOURCES=('research/shared_basis_operator_v1_plan.json','tools/shared_basis_operator_v1/__init__.py',
    'tools/shared_basis_operator_v1/geometry.py','tools/shared_basis_operator_v1/compiler.py',
    'tools/shared_basis_operator_v1/operator.py','tools/shared_basis_operator_v1/resources.py',
    'tools/probe_shared_basis_operator_v1.py','tools/audit_shared_basis_operator_v1.py',
    'tools/constrained_source_operator_v1/oracle.py','tools/constrained_source_operator_v1/prior.py',
    'tools/operator_roundoff_v1/exact_dyadic.py','tools/observer_complete_v1/frame.py',
    'tools/observer_complete_v1/audit_oracle.py','tools/locked_source_guard_v1/measurement.py',
    'tools/waveform_structured_v1/resources.py','tools/research_archive_v1.py')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','legacy-audit','primitive-audit','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from shared_basis_operator_v1.operator import Operator
    from shared_basis_operator_v1.geometry import Geometry
    from shared_basis_operator_v1.resources import describe
    from constrained_source_operator_v1 import oracle
    from locked_source_guard_v1.measurement import declared,fidelity
    from waveform_structured_v1.resources import process_memory
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',sources={},inputs={},cases=[],schema=Operator.schema)
    try:
        for name in SOURCES:
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        original=load(a.study/'report.json');legacy=load(a.legacy_audit/'report.json');primitive=load(a.primitive_audit/'report.json')
        assert not legacy['verification_passed'] and len(legacy['failures'])==19 and legacy['producer_sha256']==sha(a.study/'report.json')
        assert primitive['verification_passed'] and not primitive['whole_operator_or_constrained_solver_qualification']
        for path in (a.study/'report.json',a.legacy_audit/'report.json',a.primitive_audit/'report.json'):r['inputs'][str(path)]=sha(path)
        assert original['sources']['tools/constrained_source_operator_v1/oracle.py']==sha(repo/'tools/constrained_source_operator_v1/oracle.py')
        for case in original['cases']:
            if case['unknowns']>32:continue
            path=a.study/case['name']/'operators.npz';assert sha(path)==case['packet_sha256'];r['inputs'][str(path)]=sha(path)
            with np.load(path) as f:z={key:f[key] for key in f.files}
            carriers=oracle.table(z['orders']).copy();owned=carriers.copy();start=time.perf_counter()
            op=Operator(int(z['frames']),z['positions'],z['orders'],z['scale'],carriers,z['weights'],float(z['amplitude']),float(z['sigma']))
            carriers[:]=0;assert np.array_equal(op.g.carriers,owned)
            x=z['x'];wave=op.source(x);forward=op.full_forward(x);target=op.target_forward(x)
            adjoint=op.full_adjoint(z['full_dual']);target_dual=tuple(z['target_dual_'+str(g)] for g in range(7));target_adj=op.target_adjoint(target_dual)
            rhs=oracle.full(z,z['audio']);gradient=op.gradient(x,rhs)
            directory=a.out/case['name'];directory.mkdir()
            # Capture every actually compiled spectral block for independent
            # all-entry verification, not only dot products on chosen vectors.
            blocks={}
            for index in range(len(op.g.starts)):
                ids,matrix=op.compiler.spectral(index);assert not ids.flags.writeable and not matrix.flags.writeable
                blocks['ids_'+str(index)]=ids;blocks['matrix_'+str(index)]=matrix
            np.savez_compressed(directory/'blocks.npz',**blocks)
            arrays=dict(carriers=owned,source=wave,full_forward=forward,full_adjoint=adjoint,
                target_adjoint=target_adj,gradient=gradient,rhs=rhs)
            for g,value in enumerate(target):arrays['target_'+str(g)]=value
            if 'null_vector' in z:arrays['null_full']=op.full_forward(z['null_vector']);assert not np.count_nonzero(arrays['null_full'])
            np.savez_compressed(directory/'output.npz',**arrays)
            observed=declared(z['audio'],wave,float(z['amplitude']),z['weights'])
            details=dict(name=case['name'],frames=int(z['frames']),unknowns=op.size,
                output_sha256=sha(directory/'output.npz'),blocks_sha256=sha(directory/'blocks.npz'),
                compiled_blocks=op.compiler.compiled_blocks,cache_hits=op.compiler.cache_hits,
                cached_payload_bytes=op.compiler.cached_bytes,
                objective=float(.5*np.linalg.norm(forward-rhs)**2+op.prior.cost(x)),
                original_direct_waveform_metrics=observed,original_direct_fidelity_passed=fidelity(observed),
                method_kept_distinct_from_legacy_FFT_composition=True,
                elapsed_seconds=time.perf_counter()-start,process_memory=process_memory())
            save(directory/'report.json',details);r['cases'].append(details);save(a.out/'report.json',r)
            print('SHARED_KNOWN',case['name'],op.compiler.compiled_blocks,op.compiler.cache_hits,flush=True)
        assert len(r['cases'])==4
        # Geometry-only complete-scale accounting; no spectral factor compiled.
        frames=18430;orders=np.arange(1,289);original_nodes=np.r_[np.arange(0,frames-4096,256),frames-4097]
        positions=np.r_[np.arange(-2048,0,256),original_nodes,original_nodes[-1]+np.arange(256,2049,256)]+2048
        full=Geometry(frames,positions,orders,np.ones((288,1)),oracle.table(orders),np.ones(2049),1.,1.)
        r['full_geometry_resources']=describe(full)
        assert (full.size,len(full.positions),len(full.starts),len(full.target_slots))==(84096,73,56,40)
        assert r['full_geometry_resources']['estimated_authored_array_budget_bytes']<1024**3
        r.update(result='shared_discrete_basis_known_execution_completed',new_small_method_requires_independent_audit=True,
            full_geometry_only_not_full_operator_execution=True,original_19_failures_preserved=True,
            actual_vehicle_or_full_constrained_solver_qualification=False,new_C1_source_eligible_for_statistics=False)
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
