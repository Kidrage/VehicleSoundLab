"""Independently audit array ownership/lifetimes and conditional full shapes."""
import argparse
import inspect
import math
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','study','audit','baseline','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import scipy
    from scipy import linalg
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    source=load(a.study/'report.json');independent=load(a.audit/'report.json');baseline=load(a.baseline/'report.json')
    assert independent['result']=='independent_waveform_structured_original12_verified' and independent['pass_count']==12
    assert independent['producer_sha256']==sha(a.study/'report.json')
    qr_source=inspect.getsource(linalg.qr)
    (a.out/'scipy_qr_source.txt').write_text(qr_source,encoding='utf-8',newline='\n')
    result=dict(result='running',cases=[],alias_controls=[],inputs={str(p):sha(p) for p in
        (a.study/'report.json',a.audit/'report.json',a.baseline/'report.json')},
        dependencies=dict(numpy_version=np.__version__,scipy_version=scipy.__version__,
            scipy_qr_source_file=inspect.getsourcefile(linalg.qr),scipy_qr_source_sha256=sha(a.out/'scipy_qr_source.txt')))
    shapes=set();cumulative=[]
    for case in source['cases']:
        events=case['resources']['events'];arrays={e['name']:e for e in events if e['event']=='array'}
        stores=case['resources']['storage_bytes'];snapshots=[e for e in events if e['event']=='snapshot']
        for e in arrays.values():
            assert e['bytes']==8*math.prod(e['shape']) and e['dtype']=='float64'
            assert e['backing_bytes']==stores[e['storage']] and e['bytes']<=e['backing_bytes']
        for e in snapshots:
            assert len(e['live_storages'])==len(set(e['live_storages']))
            assert e['tracked_live_backing_bytes']==sum(stores[j] for j in e['live_storages'])
            assert e['cumulative_peak_working_set_bytes']>=e['working_set_bytes']
            cumulative.append(e['cumulative_peak_working_set_bytes'])
        measured=max(e['tracked_live_backing_bytes'] for e in snapshots)
        assert measured==case['resources']['max_tracked_live_backing_bytes']
        M=len(np.load(a.study/case['file'])['positions'])
        assert arrays['penalty.K']['shape']==arrays['penalty.L']['shape']==[M,M]
        assert arrays['wave_metric.input']['F_contiguous'] and arrays['wave_metric.input']['owns_data']
        assert (arrays['wave_metric.input']['storage']==arrays['wave_metric.L']['storage'])==case['solver']['metric_root_shares_input']
        for prefix,input_name in (('X_QR','weighted_synthesis'),('graph_QR','graph.input')):
            record=case['solver'][prefix+'_alias']
            assert (arrays[input_name]['storage']==arrays[prefix+'.raw']['storage'])==record['input_and_raw_share']
            assert (arrays[prefix+'.raw']['storage']==arrays[prefix+'.R']['storage'])==record['raw_and_R_share']
            assert arrays[prefix+'.reflectors']['storage']==arrays[prefix+'.raw']['storage']
            shapes.add(tuple(arrays[input_name]['shape']))
        assert not case['solver']['explicit_Q_or_dense_packed_R_allocated_by_solver']
        assert all('Q_explicit' not in n and 'packed_R' not in n for n in arrays)
        memory=case['process_memory'];assert memory['cumulative_peak_working_set_bytes']>=max(e['cumulative_peak_working_set_bytes'] for e in snapshots)
        result['cases'].append(dict(kind=case['kind'],label=case['label'],tracked_live_backing_bytes=measured,
            cumulative_process_peak_bytes=memory['cumulative_peak_working_set_bytes'],
            node_root_each_bytes=8*M*M,metric_root_reused=case['solver']['metric_root_shares_input'],
            X_R_distinct_from_reflectors=not case['solver']['X_QR_alias']['raw_and_R_share'],
            graph_R_distinct_from_reflectors=not case['solver']['graph_QR_alias']['raw_and_R_share']))
    assert all(x<=y for x,y in zip(cumulative,cumulative[1:]))
    # Replay allocation semantics at every distinct SMALL known-case shape;
    # no full arrays or source solve are allocated here.
    rng=np.random.default_rng(9541)
    for shape in sorted(shapes):
        X=np.array(rng.normal(size=shape),order='F')
        (raw,tau),R=linalg.qr(X,mode='raw',overwrite_a=True,check_finite=False)
        assert np.shares_memory(X,raw) and not np.shares_memory(raw,R)
        result['alias_controls'].append(dict(shape=shape,input_raw_share=True,raw_R_share=False,
            input_bytes=X.nbytes,R_bytes=R.nbytes,reflector_columns=min(shape)))
    old_peak=max(c['process_peak_working_set_bytes'] for c in baseline['cases'])
    new_peak=max(c['process_memory']['cumulative_peak_working_set_bytes'] for c in source['cases'])
    full={}
    for C in (1,2):
        m,n=12289*C,2*49*288*C;k=min(m,n)
        shapes=dict(W=(m,m),X_raw=(m,n),X_R=(k,n),graph_raw=(k+n,k),graph_R=(k,k))
        sizes={n:8*math.prod(s) for n,s in shapes.items()}
        # These five stores coexist at graph QR under THIS implementation's
        # observed alias model. Their union is only an array subtotal, not a
        # peak-RAM prediction: temporaries/workspaces/other inputs still exist.
        full[str(C)]=dict(frames_total=m,source_columns=n,shapes=shapes,individual_bytes=sizes,
            conditional_coexisting_registered_array_subtotal=sum(sizes.values()),
            source_packed_penalty_each_bytes=8*(2*49*288*C)**2,actual_node_root_each_bytes=8*49**2,
            conditional_not_allocated_or_measured=True,full_feasibility_proven=False)
    diagnostic=[c for c in independent['cases'] if not c['stricter_whitened_2e_11_diagnostic_passed']]
    result.update(result='independent_waveform_structured_resources_verified',
        known_case_count=12,original12_qualified=12,previous_cumulative_peak_bytes=old_peak,
        current_cumulative_peak_bytes=new_peak,cumulative_peak_reduction_fraction=1-new_peak/old_peak,
        original_equation_audit_gate=2e-8,stricter_whitened_diagnostic_failures=[c['label'] for c in diagnostic],
        previous_identical_diagnostic_discrepancies_retained=True,full_conditional_arrays=full,
        no_full_or_source_allocation=True,no_SHARC_cycle_conversion=True,
        auditor_sha256=sha(__file__))
    save(a.out/'report.json',result)
    print({k:result[k] for k in ('result','previous_cumulative_peak_bytes','current_cumulative_peak_bytes',
                               'cumulative_peak_reduction_fraction','stricter_whitened_diagnostic_failures','full_conditional_arrays')},flush=True)


if __name__=='__main__':main()
