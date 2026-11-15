"""Independent native/no-T ownership, phase release and same-result audit."""
import argparse
import math
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','study','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from waveform_correction_v1.problem import restore
    from waveform_correction_v1.trace import original_frobenius
    from run_waveform_stream_full_v1 import physical_memory
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    shutil.copy2(repo/'tools/waveform_correction_v1/trace.py',a.out/'executed_production_trace.py')
    r=dict(result='running',cases=[],trace_controls=[],inputs={},producer_bindings={})
    def read(path):r['inputs'][str(path)]=sha(path);return load(path)
    try:
        controls=read(a.study/'controls_audit1/report.json')
        assert controls['all_qualified'] and controls['inverse_backend']=='native'
        previous=a.workspace/'baselines/waveform_original_correction_v1'
        assert sha(previous/'manifest.json')==load(repo/'research/waveform_original_correction_v1_summary.json')['manifest_sha256']
        r['inputs'][str(previous/'manifest.json')]=sha(previous/'manifest.json')
        for prefix,kind,count,oldfolder in (('known','original12',12,'known1'),('shared','shared8',8,'shared1'),
                ('pipeline_known','original12',12,'known1'),('pipeline_shared','shared8',8,'shared1')):
            folder=a.study/(prefix+'1');source=read(folder/'report.json');audit=read(a.study/(prefix+'_audit1')/'report.json')
            assert source['result']=='waveform_original_operator_correction_known_measured' and source['inverse_backend']=='native'
            assert audit['all_qualified'] and audit['pass_count']==count and audit['producer_sha256']==sha(folder/'report.json')
            r['producer_bindings'][prefix]=sha(folder/'report.json')
            old=read(previous/'evidence'/oldfolder/'report.json')
            parents={(c['kind'],c['label']):c for c in old['cases']}
            for case in source['cases']:
                path=folder/case['file'];assert sha(path)==case['sha256'];r['inputs'][str(path)]=sha(path)
                before=parents[case['kind'],case['label']];oldpath=previous/'evidence'/oldfolder/before['file']
                assert sha(oldpath)==before['sha256'];r['inputs'][str(oldpath)]=sha(oldpath)
                with np.load(path) as z,np.load(oldpath) as original:
                    exact=[]
                    for n in ('q','z','wave_model_residual','history_z','history_wave','history_original_normal','delta_z'):
                        assert np.array_equal(z[n],original[n]),(prefix,case['label'],n)
                        exact.append(n)
                    assert 'inverse_inner_T' not in z
                    if prefix=='pipeline_known' or prefix=='pipeline_shared':
                        base={n:z[n] for n in ('audio','positions','orders','scale')}
                        if case['kind']=='Hann':
                            system,prior,_,_,_=restore(kind,case,base)
                            trace=original_frobenius(z['positions'],z['orders'],z['scale'],system.metric,prior.L,z['audio'].shape[1])
                            independently_measured=next(c['complete_original_Frobenius'] for c in audit['cases'] if c['kind']==case['kind'] and c['label']==case['label'])
                            err=abs(trace['root_Frobenius']-independently_measured)/max(1.,independently_measured)
                            assert err<2e-12
                            r['trace_controls'].append(dict(kind=case['kind'],label=case['label'],channels=z['audio'].shape[1],
                                complete_original_Frobenius=independently_measured,relative_error=err,qualified=True))
                events,stores=case['resources']['events'],case['resources']['storage_bytes']
                arrays={v['name']:v for v in events if v['event']=='array'}
                snapshots={v['phase']:v for v in events if v['event']=='snapshot'}
                for v in arrays.values():
                    assert v['dtype']=='float64' and v['bytes']==8*math.prod(v['shape'])
                    assert v['backing_bytes']==stores[v['storage']]
                for v in snapshots.values():
                    assert len(v['live_storages'])==len(set(v['live_storages']))
                    assert v['tracked_live_backing_bytes']==sum(stores[i] for i in v['live_storages'])
                for pre,name in (('correction.right_QR','correction.right_input'),('correction.inner_QR','correction.inner_input')):
                    assert arrays[pre+'.raw']['storage']==arrays[name]['storage']==arrays[pre+'.reflectors']['storage']
                assert 'correction.inner_QR.square_R' not in arrays
                assert not case['factor']['separate_square_T_allocated']
                assert case['factor']['native_triangle_aliases_inner_raw']
                if source.get('pipeline',False):
                    oldids={arrays[n]['storage'] for n in ('wave_metric.L_banded','graph_QR.raw','graph_QR.square_R')}
                    released=snapshots['pipeline.old_metric_graph_T_released']
                    assert not oldids.intersection(released['live_storages'])
                    for phase in ('correction.right_QR.factored_with_work','correction.inner_QR.factored_with_work'):
                        assert not oldids.intersection(snapshots[phase]['live_storages'])
                    sourceid=arrays['weighted_synthesis']['storage']
                    assert sourceid not in snapshots['pipeline.source_QR_released']['live_storages']
                    assert sourceid not in snapshots['pipeline.original_correction_complete']['live_storages']
                r['cases'].append(dict(prefix=prefix,kind=case['kind'],label=case['label'],exact_arrays=exact,
                    no_correction_square_T=True,actual_pipeline_release_verified=source.get('pipeline',False),
                    registered_peak=case['resources']['max_tracked_live_backing_bytes'],
                    cumulative_process_peak=case['process_memory']['cumulative_peak_working_set_bytes']))
        assert len(r['cases'])==40 and len(r['trace_controls'])==13
        N,M=12289,49;n=2*M*288;k=min(N,n)
        base=dict(W_band=8*4096*N,X_raw=8*N*n,graph_raw=8*(k+n)*k,graph_T=8*k*k)
        correction=dict(X_raw=8*N*n,right=8*n*k,inner=16*k*k)
        main=max(sum(base.values()),sum(correction.values()));memory=physical_memory()
        reserve,headroom=3*1024**3//2,3*1024**3;required=main+reserve+headroom
        r.update(result='independent_waveform_correction_storage_verified',original12=12,shared8=8,
            both_native_and_pipeline_same_as_previous=True,all_actual_phase_releases_verified=True,
            production_trace_controls=13,original_full_conditional=dict(frames=N,nodes=M,orders=288,RHS=2,
                base_arrays=base,correction_arrays=correction,main_arrays_only=main,
                native_allowance=reserve,headroom=headroom,required_available=required,
                current_memory=memory,available_gate_passed=min(memory['available_physical_bytes'],memory['available_commit_bytes'])>=required,
                NOT_full_peak_or_feasibility_proof=True),auditor_sha256=sha(__file__),
            trace_source_sha256=sha(repo/'tools/waveform_correction_v1/trace.py'),full_or_source_or_runtime_qualified=False)
        save(a.out/'report.json',r);print(r['result'],'40cases/13trace',r['original_full_conditional'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
