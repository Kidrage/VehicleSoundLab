"""One complete-width known block benchmark after small-method audit and budget."""
import argparse
import ctypes
import hashlib
import os
from pathlib import Path
import shutil
import sys
import time
from research_archive_v1 import load,save,sha


def available_memory():
    class Status(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in
            ('physical','available','page','available_page','virtual','available_virtual','extended')]
    s=Status();s.length=ctypes.sizeof(s)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s)):raise OSError('Memory preflight unavailable')
    return int(s.available)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','audit','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from shared_basis_operator_v1.operator import Operator
    from constrained_source_operator_v1.oracle import table
    from waveform_structured_v1.resources import process_memory
    a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},inputs={})
    try:
        repo=Path(__file__).resolve().parents[1];study=load(a.study/'report.json');audit=load(a.audit/'report.json')
        assert audit['verification_passed'] and audit['producer_sha256']==sha(a.study/'report.json')
        assert not audit['full_scale_operator_or_constrained_solver_or_actual_source_qualification']
        names=set(study['sources'])|{'tools/bench_shared_basis_block_v1.py','tools/audit_shared_basis_support_v1.py'}
        for name in names:
            path=repo/name
            if name in study['sources']:assert sha(path)==study['sources'][name]
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest);r['sources'][name]=sha(dest)
        for path in (a.study/'report.json',a.audit/'report.json'):r['inputs'][str(path)]=sha(path)
        budget=study['full_geometry_resources'];available=available_memory()
        assert budget['estimated_authored_array_budget_bytes']<1024**3 and available>budget['estimated_authored_array_budget_bytes']+2*1024**3
        r['memory_preflight']=dict(available_physical_bytes=available,authored_array_budget_bytes=budget['estimated_authored_array_budget_bytes'],reserve_bytes=2*1024**3)
        frames=18430;orders=np.arange(1,289);original=np.r_[np.arange(0,frames-4096,256),frames-4097]
        positions=np.r_[np.arange(-2048,0,256),original,original[-1]+np.arange(256,2049,256)]+2048
        op=Operator(frames,positions,orders,np.ones((288,1)),table(orders),np.ones(2049),1.,1.,cache_bytes=0)
        index=max(budget['shared_spectral_blocks'],key=lambda v:v['matrix_bytes'])['index']
        r['single_block']=dict(index=index,original_full_nodes=73,original_full_orders=288,
            no_actual_recording_or_source_factor_input=True,cache_bytes=0)
        save(a.out/'report.json',r);print('COMPILE_FULL_KNOWN_SHARED_BLOCK',index,flush=True)
        start=time.perf_counter();ids,matrix=op.compiler.spectral(index);compile_seconds=time.perf_counter()-start
        rng=np.random.default_rng(2026111702);x=rng.standard_normal((len(ids),2));y=rng.standard_normal((4098,2))
        start=time.perf_counter();forward=matrix@x;forward_seconds=time.perf_counter()-start
        start=time.perf_counter();adjoint=matrix.T@y;adjoint_seconds=time.perf_counter()-start
        dot_error=float(abs(np.sum(forward*y)-np.sum(x*adjoint))/max(np.linalg.norm(forward)*np.linalg.norm(y),1e-300))
        assert dot_error<2e-11 and matrix.nbytes==budget['maximum_spectral_block_bytes']
        payload_hash=hashlib.sha256(memoryview(matrix).cast('B')).hexdigest()
        np.savez_compressed(a.out/'probe.npz',ids=ids,x=x,y=y,forward=forward,adjoint=adjoint)
        r.update(result='single_complete_width_known_shared_block_benchmarked',
            block_rows=matrix.shape[0],block_columns=matrix.shape[1],block_payload_bytes=matrix.nbytes,
            compile_seconds=compile_seconds,forward_seconds=forward_seconds,adjoint_seconds=adjoint_seconds,
            dot_scaled_error=dot_error,process_memory=process_memory(),compiled_block_sha256=payload_hash,
            probe_sha256=sha(a.out/'probe.npz'),only_one_of_56_spectral_blocks_executed=True,
            no_full_operator_convergence_fidelity_or_solver_timing_qualification=True,
            no_actual_fit_or_factor_files_C_or_new_audio=True,new_C1_source_eligible_for_statistics=False)
        save(a.out/'report.json',r);print(r['result'],compile_seconds,forward_seconds,adjoint_seconds,flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
