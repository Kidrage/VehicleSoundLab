"""Independent known-case result/lifetime/accounting and ownership guard audit."""
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
    from waveform_early_release_v1.inverse import OwnedNativeInverse
    from waveform_structured_v1.resources import ArrayLedger
    from run_waveform_stream_full_v1 import physical_memory
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',cases=[],ownership_guards=[],inputs={})
    def read(path):r['inputs'][str(path)]=sha(path);return load(path)
    try:
        for folder in ('controls_audit1','roots_audit1'):
            assert read(a.study/folder/'report.json')['all_qualified']
        assert read(a.study/'roots_native_audit1/report.json')['result']=='independent_waveform_banded_controls_passed'
        oldroot=a.workspace/'baselines/waveform_correction_storage_v1'
        assert sha(oldroot/'manifest.json')==load(repo/'research/waveform_correction_storage_v1_summary.json')['manifest_sha256']
        r['inputs'][str(oldroot/'manifest.json')]=sha(oldroot/'manifest.json')
        entries={row['path']:row['sha256'] for row in load(oldroot/'manifest.json')['files']}
        for prefix,count,previous in (('known',12,'pipeline_known1'),('shared',8,'pipeline_shared1')):
            producer=read(a.study/(prefix+'1')/'report.json')
            audit=read(a.study/(prefix+'_audit1')/'report.json')
            assert producer['all_qualified'] and audit['all_qualified'] and audit['pass_count']==count
            assert audit['producer_sha256']==sha(a.study/(prefix+'1')/'report.json')
            old=read(oldroot/'evidence'/previous/'report.json')
            assert sha(oldroot/'evidence'/previous/'report.json')==entries['evidence/'+previous+'/report.json']
            by_key={(c['kind'],c['label']):c for c in old['cases']}
            for case in producer['cases']:
                path=a.study/(prefix+'1')/case['file'];assert sha(path)==case['sha256'];r['inputs'][str(path)]=sha(path)
                prior=by_key[case['kind'],case['label']];before=oldroot/'evidence'/previous/prior['file']
                assert sha(before)==prior['sha256']==entries[before.relative_to(oldroot).as_posix()]
                r['inputs'][str(before)]=sha(before)
                comparison=[]
                with np.load(path) as now,np.load(before) as original:
                    for key in ('q','z','wave_model_residual','history_z','history_wave','history_original_normal','delta_z'):
                        error=float(np.max(abs(now[key]-original[key]))/max(1.,float(np.max(abs(original[key])))))
                        assert error<2e-11,(case['label'],key,error)
                        comparison.append(dict(array=key,bitwise_exact=np.array_equal(now[key],original[key]),
                                               max_relative_to_unit_or_peak=error))
                    assert 'inverse_inner_T' not in now
                events=case['resources']['events'];stores=case['resources']['storage_bytes']
                arrays={e['name']:e for e in events if e['event']=='array'}
                snapshots={e['phase']:e for e in events if e['event']=='snapshot'}
                for row in arrays.values():
                    assert row['bytes']==8*math.prod(row['shape']) and row['backing_bytes']==stores[row['storage']]
                for row in snapshots.values():
                    assert len(row['live_storages'])==len(set(row['live_storages']))
                    assert row['tracked_live_backing_bytes']==sum(stores[i] for i in row['live_storages'])
                assert 'graph_QR.square_R' not in arrays and 'correction.inner_QR.square_R' not in arrays
                graphid=arrays['graph_QR.raw']['storage'];sourceid=arrays['X_QR.raw']['storage']
                oldids={graphid,arrays['wave_metric.L_banded']['storage']}
                assert graphid==arrays['graph.native_triangle_storage']['storage']==arrays['graph.input']['storage']
                assert sourceid==arrays['weighted_synthesis']['storage']
                native=case['pipeline_info']['base_solver']
                assert not native['graph_triangular_explicit_F_copy'] and native['graph_triangle_aliases_raw']
                assert native['graph_triangle_leading_dimension']==arrays['graph_QR.raw']['shape'][0]
                for phase in ('pipeline.old_metric_graph_T_released','correction.right_QR.factored_with_work',
                              'owned_inverse.source_released_before_inner','correction.inner_QR.factored_with_work'):
                    assert not oldids.intersection(snapshots[phase]['live_storages'])
                rightid=arrays['correction.right_QR.raw']['storage'];innerid=arrays['correction.inner_QR.raw']['storage']
                assert sourceid in snapshots['correction.right_QR.factored_with_work']['live_storages']
                early=snapshots['owned_inverse.source_released_before_inner']['live_storages']
                assert sourceid not in early and rightid in early and innerid not in early
                for phase in ('correction.inner_QR.factored_with_work','pipeline.original_correction_complete'):
                    assert sourceid not in snapshots[phase]['live_storages']
                assert next(i for i,e in enumerate(events) if e.get('phase')=='owned_inverse.source_released_before_inner') < next(i for i,e in enumerate(events) if e.get('name')=='correction.inner_input')
                for pre,key in (('correction.right_QR','correction.right_input'),('correction.inner_QR','correction.inner_input')):
                    assert arrays[pre+'.raw']['storage']==arrays[key]['storage']==arrays[pre+'.reflectors']['storage']
                assert case['factor']['source_QR_released_before_inner'] and case['factor']['native_triangle_aliases_inner_raw']
                assert not case['factor']['separate_square_T_allocated']
                r['cases'].append(dict(kind=prefix,label=case['label'],comparison=comparison,
                    actual_source_release_before_inner_verified=True,no_base_or_inverse_T_copy=True,
                    registered_peak=case['resources']['max_tracked_live_backing_bytes'],
                    cumulative_WS_peak=case['process_memory']['cumulative_peak_working_set_bytes']))
        # Exercise actual new ownership errors. The externally retained source
        # must reject BEFORE allocating inner storage, not merely claim release.
        cases=[('not_holder',None),('empty',[]),('two_items',[None,None]),
               ('float32',[np.ones((4,3),dtype=np.float32,order='F')]),
               ('row_major',[np.ones((4,3),order='C')]),
               ('borrowed_view',[np.ones((4,3),order='F')[:,:]]),
               ('nonfinite',[np.full((4,3),np.nan,order='F')])]
        retained=np.array(np.arange(12).reshape(4,3),order='F',dtype=float)
        cases.append(('retained_source',[retained]))
        for label,holder in cases:
            ledger=ArrayLedger();error=None
            try:OwnedNativeInverse(holder,ledger,block=3)
            except (ValueError,RuntimeError) as e:error=repr(e)
            assert error and not any(e.get('name')=='correction.inner_input' for e in ledger.events)
            if label=='retained_source':assert 'still owned elsewhere' in error
            r['ownership_guards'].append(dict(label=label,error=error,inner_not_allocated=True))
        N,M,H=12289,49,288;n=2*M*H;k=min(N,n)
        W,X,graph,T=8*4096*N,8*N*n,8*(k+n)*k,8*k*k
        right,inner=8*n*k,16*k*k
        major=max(W+X+graph,X+right,right+inner)
        required=major+3*1024**3//2+3*1024**3
        memory=physical_memory()
        r.update(result='independent_waveform_early_release_known_verified',
            all_original12_shared8_qualified=True,actual_lifetimes_verified=True,
            all_output_arrays_bitwise_previous=all(x['bitwise_exact'] for c in r['cases'] for x in c['comparison']),
            full_conditional=dict(frames=N,nodes=M,orders=H,RHS=2,base_main_arrays=W+X+graph,
                correction_phases=[X+right,right+inner],main_arrays_only=major,
                prior_native_main_arrays=max(W+X+graph+T,X+right+inner),required_available=required,
                available_memory=memory,available_gate_passed=min(memory['available_physical_bytes'],memory['available_commit_bytes'])>=required,
                conditional_NOT_actual_full_peak=True),auditor_sha256=sha(__file__),full_or_source_or_runtime_qualified=False)
        save(a.out/'report.json',r);print(r['result'],'exact',r['all_output_arrays_bitwise_previous'],'full',r['full_conditional'],flush=True)
    except BaseException as e:
        r.update(result='failed',error=repr(e));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
