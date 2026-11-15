"""Actual known band ownership/BLAS shapes and conditional full/real resources."""
import argparse
import hashlib
import math
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','known','audit','shared','shared-audit','context','out'):
        p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from run_waveform_stream_full_v1 import physical_memory
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',cases=[],native_shape_replays=[],conditional_cases=[],inputs={})
    def read(folder):
        path=folder/'report.json';r['inputs'][str(path)]=sha(path);return load(path)
    try:
        known,ka,shared,sa,context=[read(path) for path in (a.known,a.audit,a.shared,a.shared_audit,a.context)]
        assert ka['pass_count']==12 and ka['all_qualified'] and ka['producer_sha256']==sha(a.known/'report.json')
        assert sa['pass_count']==7 and not sa['all_qualified'] and sa['producer_sha256']==sha(a.shared/'report.json')
        assert context['result']=='waveform_native_context_provenance_inspected'
        shapes=set()
        for source in (known,shared):
            assert source['backend']=='banded'
            for case in source['cases']:
                assert sha((a.known if source is known else a.shared)/case['file'])==case['sha256']
                events=case['resources']['events'];stores=case['resources']['storage_bytes']
                arrays={e['name']:e for e in events if e['event']=='array'}
                snapshots=[e for e in events if e['event']=='snapshot']
                for e in arrays.values():
                    assert e['bytes']==8*math.prod(e['shape']) and e['backing_bytes']==stores[e['storage']]
                for e in snapshots:
                    assert len(e['live_storages'])==len(set(e['live_storages']))
                    assert e['tracked_live_backing_bytes']==sum(stores[i] for i in e['live_storages'])
                assert arrays['wave_metric.input']['storage']==arrays['wave_metric.L_banded']['storage']
                assert 'wave_metric.L' not in arrays and arrays['wave_metric.input']['F_contiguous']
                if case['kind']=='Hann':
                    assert arrays['wave_metric.input']['shape'][0]==4096
                    assert arrays['wave_metric.input']['shape'][1]==case['solver']['waveform_rows']
                    shapes.add(tuple(arrays['wave_metric.input']['shape']))
                for prefix,input_name in (('X_QR','weighted_synthesis'),('graph_QR','graph.input')):
                    assert arrays[prefix+'.raw']['storage']==arrays[input_name]['storage']
                    assert arrays[prefix+'.reflectors']['storage']==arrays[input_name]['storage']
                    assert prefix+'.R' not in arrays
                assert arrays['graph_QR.square_R']['storage']!=arrays['graph_QR.raw']['storage']
                assert arrays['graph_QR.square_R']['F_contiguous']
                peak=max(e['tracked_live_backing_bytes'] for e in snapshots)
                assert peak==case['resources']['max_tracked_live_backing_bytes']
                r['cases'].append(dict(kind=case['kind'],label=case['label'],qualified=case['qualified'],
                    tracked_live_backing_bytes=peak,band_shape=arrays['wave_metric.input']['shape'],
                    metric_input_and_root_one_store=True,explicit_square_graph_copy_retained=True,
                    actual_cumulative_process_peak=case['process_memory']['cumulative_peak_working_set_bytes']))
        rng=np.random.default_rng(396107)
        for S,N in sorted(shapes):
            band=np.zeros((S,N),order='F');band[0]=1.1;band[1,:N-1]=.01;band[7,:N-7]=.001
            before=hashlib.sha256(memoryview(band.ravel(order='F'))).hexdigest()
            rhs=np.array(rng.normal(size=(N,3)),order='F');aliases=[]
            for inverse in (False,True):
                for transpose in (False,True):
                    fn=linalg.get_blas_funcs('tbsv' if inverse else 'tbmv',(band,))
                    expected=rhs.copy()
                    if inverse:
                        for i in (range(N-1,-1,-1) if transpose else range(N)):
                            value=rhs[i].copy()
                            for step,gain in ((1,.01),(7,.001)):
                                j=i+step if transpose else i-step
                                if 0<=j<N:value-=gain*expected[j]
                            expected[i]=value/1.1
                    else:
                        expected*=1.1
                        for step,gain in ((1,.01),(7,.001)):
                            if transpose:expected[:-step]+=gain*rhs[step:]
                            else:expected[step:]+=gain*rhs[:-step]
                    got=np.array(rhs,order='F')
                    for j in range(3):
                        out=fn(S-1,band,got[:,j],lower=1,trans=int(transpose),overwrite_x=1)
                        assert np.shares_memory(out,got[:,j])
                    error=float(np.max(abs(got-expected))/max(1.,abs(expected).max()));assert error<2e-12
                    aliases.append(dict(inverse=inverse,transpose=transpose,all_three_outputs_alias=True,error=error))
            assert hashlib.sha256(memoryview(band.ravel(order='F'))).hexdigest()==before
            r['native_shape_replays'].append(dict(shape=[S,N],aliases=aliases,
                probe='Declared sparse triangular fixture at actual packed shape; no dense expansion'))
        memory=physical_memory();r['available_memory']=memory
        def budget(N,M,label):
            n=2*M*288;k=min(N,n)
            sizes=dict(W_band=8*4096*N,X_raw=8*N*n,graph_raw=8*(k+n)*k,graph_R=8*k*k)
            dense_W=8*N*N;subtotal=sum(sizes.values());required=subtotal+3*1024**3//2+3*1024**3
            return dict(label=label,frames=N,nodes=M,orders=288,independent_RHS=2,
                individual_bytes=sizes,coexisting_four_array_bytes=subtotal,
                avoided_dense_metric_bytes=dense_W-sizes['W_band'],
                native_and_temporary_allowance_bytes=3*1024**3//2,headroom_bytes=3*1024**3,
                required_available=required,
                current_headroom_passed=min(memory['available_physical_bytes'],memory['available_commit_bytes'])>=required,
                conditional_only_NOT_allocated=True)
        r['conditional_cases'].append(budget(12289,49,'full_known'))
        for c in context['cases']:
            r['conditional_cases'].extend((budget(c['frames'],c['nodes'],c['label']+' original'),
                budget(c['frames']+4096,c['nodes']+16,c['label']+' proposed_context')))
        previous=a.workspace/'baselines/waveform_stream_v1/evidence/known1/report.json'
        dense=load(previous);r['inputs'][str(previous)]=sha(previous)
        oldpeak=max(c['process_memory']['cumulative_peak_working_set_bytes'] for c in dense['cases'])
        newpeak=max(c['process_memory']['cumulative_peak_working_set_bytes'] for c in known['cases'])
        failed=[c for c in sa['cases'] if not c['qualified']]
        assert len(failed)==1 and failed[0]['label']=='delayed_right'
        r.update(result='independent_waveform_banded_resources_inspected',known12_qualified=12,shared8_qualified=7,
            shared_qualification_failure_retained=failed,
            old_root_strict_Gram_failures=[c['label'] for c in ka['cases'] if not c['old_root_Gram_2e_11_passed']],
            original_known_cumulative_peak_before=oldpeak,original_known_cumulative_peak_after=newpeak,
            observed_working_set_peak_reduction_fraction=1-newpeak/oldpeak,
            known_runtime_seconds=sum(c['elapsed_seconds'] for c in known['cases']),
            previous_known_runtime_seconds=sum(c['elapsed_seconds'] for c in dense['cases']),
            no_full_or_real_run_authorized_by_this_audit=True,
            full_or_real_or_runtime_or_hearing_qualified=False,auditor_sha256=sha(__file__))
        save(a.out/'report.json',r);print(r['result'],'peaks',oldpeak,newpeak,'shared',7,flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
