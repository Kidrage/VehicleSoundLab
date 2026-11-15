"""Actual GEQRF/ORMQR aliases, work arrays and conditional full shared geometry."""
import argparse
import inspect
import math
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','known','audit','shared','shared-audit','out'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import scipy
    from scipy import linalg
    from waveform_stream_v1.householder import Householder
    from waveform_structured_v1.resources import ArrayLedger
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    known,ka,shared,sa=[load(p/'report.json') for p in (a.known,a.audit,a.shared,a.shared_audit)]
    assert ka['all_qualified'] and ka['pass_count']==12 and ka['producer_sha256']==sha(a.known/'report.json')
    assert sa['all_qualified'] and sa['pass_count']==8 and sa['producer_sha256']==sha(a.shared/'report.json')
    source=inspect.getsource(linalg.solve_triangular)
    (a.out/'scipy_solve_triangular_source.txt').write_text(source,encoding='utf-8',newline='\n')
    r=dict(result='running',cases=[],alias_replays=[],inputs={str(p/'report.json'):sha(p/'report.json') for p in
        (a.known,a.audit,a.shared,a.shared_audit)},dependencies=dict(numpy=np.__version__,scipy=scipy.__version__,
        triangular_source_sha256=sha(a.out/'scipy_solve_triangular_source.txt')))
    shapes=set()
    for study in (known,shared):
        for case in study['cases']:
            events=case['resources']['events'];stores=case['resources']['storage_bytes']
            arrays={e['name']:e for e in events if e['event']=='array'}
            snapshots=[e for e in events if e['event']=='snapshot']
            for e in arrays.values():
                assert e['bytes']==8*math.prod(e['shape']) and e['dtype']=='float64'
                assert e['backing_bytes']==stores[e['storage']] and e['bytes']<=e['backing_bytes']
            for e in snapshots:
                assert len(e['live_storages'])==len(set(e['live_storages']))
                assert e['tracked_live_backing_bytes']==sum(stores[j] for j in e['live_storages'])
                assert e['cumulative_peak_working_set_bytes']>=e['working_set_bytes']
            peak=max(e['tracked_live_backing_bytes'] for e in snapshots)
            assert peak==case['resources']['max_tracked_live_backing_bytes']
            for prefix,input_name in (('X_QR','weighted_synthesis'),('graph_QR','graph.input')):
                assert arrays[prefix+'.raw']['storage']==arrays[input_name]['storage']
                assert arrays[prefix+'.reflectors']['storage']==arrays[input_name]['storage']
                assert prefix+'.R' not in arrays
                assert not case['solver'][prefix+'_alias']['rectangular_R_allocated']
                shapes.add(tuple(arrays[input_name]['shape']))
            assert arrays['graph_QR.square_R']['F_contiguous']
            assert arrays['graph_QR.square_R']['storage']!=arrays['graph_QR.raw']['storage']
            assert arrays['wave_metric.input']['storage']==arrays['wave_metric.L']['storage']
            assert not case['solver']['rectangular_R_or_explicit_Q_or_dense_packed_R_allocated_by_solver']
            r['cases'].append(dict(kind=case['kind'],label=case['label'],tracked_live_backing_bytes=peak,
                cumulative_process_peak=case['process_memory']['cumulative_peak_working_set_bytes'],
                X_shape=arrays['weighted_synthesis']['shape'],graph_shape=arrays['graph.input']['shape'],
                observed_geqrf_work_bytes=[arrays[p+'.geqrf_work']['bytes'] for p in ('X_QR','graph_QR')]))
    # Replay at EVERY actual known shape; raw input, work outputs and factor
    # ownership are observed, never inferred from overwrite=True.
    rng=np.random.default_rng(740983)
    for shape in sorted(shapes):
        matrix=np.array(rng.normal(size=shape),order='F');before=matrix.copy()
        ledger=ArrayLedger();qr=Householder(matrix,ledger,'replay')
        assert np.shares_memory(matrix,qr.raw)
        k=min(shape);F=np.triu(qr.raw[:k])
        Q=qr.apply(np.eye(shape[0],k))
        error=float(np.linalg.norm(Q@F-before)/max(np.linalg.norm(before),1e-300));assert error<2e-12
        rhs=rng.normal(size=(shape[0],2));answer=qr.apply(rhs)
        assert np.isfinite(answer).all()
        if shape[0]>=shape[1]:
            T=qr.square_triangular();assert T.flags.f_contiguous and not np.shares_memory(T,qr.raw)
            oldT=T.copy()
            b=np.array(rng.normal(size=(k,2)),order='F');saved=b.copy()
            trtrs=linalg.get_lapack_funcs('trtrs',(T,b))
            out,flag=trtrs(T,b,overwrite_b=True);assert flag==0
            assert np.shares_memory(out,b) and np.array_equal(T,oldT)
            terr=float(np.linalg.norm(T@out-saved)/np.linalg.norm(saved));assert terr<2e-10
        r['alias_replays'].append(dict(shape=shape,input_raw_share=True,rectangular_R_absent=True,
            geqrf_lwork=qr.lwork,reconstruction_error=error,library='direct '+str(linalg.get_lapack_funcs('geqrf',(matrix,)))))
    m,n=12289,2*49*288;k=min(m,n)
    shapes=dict(W=(m,m),X_raw=(m,n),graph_raw=(k+n,k),graph_square_R=(k,k))
    sizes={name:8*math.prod(shape) for name,shape in shapes.items()}
    old_path=a.workspace/'baselines/waveform_structured_v1/evidence/resources_audit1/report.json'
    old=load(old_path);r['inputs'][str(old_path)]=sha(old_path)
    strict=[c['label'] for c in ka['cases'] if not c['stricter_whitened_2e_11_diagnostic_passed']]
    assert len(strict)==8
    r.update(result='independent_waveform_stream_resources_verified',known12_qualified=True,shared8_qualified=True,
        original12_cumulative_process_peak_bytes=max(c['process_memory']['cumulative_peak_working_set_bytes'] for c in known['cases']),
        previous_original12_cumulative_peak_bytes=old['current_cumulative_peak_bytes'],
        shared8_separate_process_peak_bytes=max(c['process_memory']['cumulative_peak_working_set_bytes'] for c in shared['cases']),
        strict_white_diagnostic_failures_retained=strict,
        full_shared_two_RHS_conditional_arrays=dict(frames=12289,nodes=49,orders=288,independent_RHS=2,
            shapes=shapes,individual_bytes=sizes,coexisting_four_array_subtotal=sum(sizes.values()),
            avoided_rectangular_X_R_bytes=8*k*n,per_node_matrix_bytes=8*49**2,
            NOT_peak_prediction=True,full_not_allocated=True,full_feasibility_proven=False),
        scope='Registered arrays, returned LAPACK work arrays and separate cumulative process peaks; unregistered/BLAS native allocations and full headroom remain unproven',
        auditor_sha256=sha(__file__),no_full_source_C_audio_or_SHARC_qualification=True)
    save(a.out/'report.json',r);print(r['result'],r['full_shared_two_RHS_conditional_arrays'],flush=True)


if __name__=='__main__':main()
