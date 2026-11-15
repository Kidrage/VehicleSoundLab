"""Independent archived native pipeline/full-known and exact source bindings."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('archive','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    def read(path):return json.loads(path.read_text(encoding='utf-8'))
    def sha(path):
        with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
    e=a.archive/'evidence';v=read(a.archive/'validation.json')
    assert {p.name for p in e.iterdir() if p.is_dir()}==set(v['selected_terminal_evidence_directories'])
    parents={}
    for name,digest in v['upstream_manifests_sha256'].items():
        path=a.archive/f'inputs/upstream/{name}/manifest.json';assert sha(path)==digest
        parents[name]={r['path']:r['sha256'] for r in read(path)['files']}
    sources=inputs=files=0
    for folder in v['selected_terminal_evidence_directories']:
        r=read(e/folder/'report.json')
        if 'auditor_sha256' in r:
            executed=e/folder/('executed_inspection.py' if folder=='real_resources1' else 'executed_audit.py')
            assert sha(executed)==r['auditor_sha256']
        for name,digest in r.get('inputs',{}).items():
            target=v['original_input_archive_locations'][name];assert sha(a.archive/target)==digest
            parts=Path(target).parts
            if parts[:2]==('inputs','upstream'):
                leaf=Path(*parts[3:]).as_posix()
                assert (v['upstream_manifests_sha256'][parts[2]] if leaf=='manifest.json' else parents[parts[2]][leaf])==digest
            inputs+=1
        for name,digest in r.get('sources',{}).items():
            assert sha(e/folder/'exact_sources'/name)==digest;sources+=1
        for key in ('cases','inverse_cases','original_cases'):
            for case in r.get(key,[]):
                if 'file' in case and 'sha256' in case:
                    assert sha(e/folder/case['file'])==case['sha256'];files+=1
        if 'capture_sha256' in r:
            assert sha(e/folder/'capture.npz')==r['capture_sha256'];files+=1
    def report(n):return read(e/n/'report.json')
    controls=report('controls_audit1')
    assert controls['all_qualified'] and controls['inverse_backend']=='native'
    assert len(controls['inverse_cases'])==v['inverse_controls']==8
    assert len(controls['original_cases'])==v['arbitrary_controls']==7
    assert controls['producer_sha256']==sha(e/'controls1/report.json')
    for producer,auditor,count in (('known1','known_audit1',12),('shared1','shared_audit1',8),
            ('pipeline_known1','pipeline_known_audit1',12),('pipeline_shared1','pipeline_shared_audit1',8)):
        source,audit=report(producer),report(auditor)
        assert source['all_qualified'] and audit['all_qualified'] and audit['pass_count']==count
        assert audit['producer_sha256']==sha(e/producer/'report.json')
        assert audit['auditor_sha256']==sha(e/auditor/'executed_audit.py')
        assert audit['inverse_backend']=='native' and len(audit['cases'])==count
        for case in audit['cases']:
            assert case['qualified'] and case['original_gradient']<2e-7
            assert case['stable_complete_normal']<=1e-11 and case['original_backward']<=1e-11
    failed,storage=report('storage_audit1'),report('storage_audit2')
    assert failed['result']=='failed' and 'KeyError' in failed['error'] and 'pipeline' in failed['error']
    assert sha(e/'storage_audit1/executed_audit.py')!=sha(e/'storage_audit2/executed_audit.py')
    assert storage['result']=='independent_waveform_correction_storage_verified'
    assert len(storage['cases'])==v['known_exact_array_case_count']==40
    assert len(storage['trace_controls'])==v['production_trace_known_controls']==13
    assert storage['all_actual_phase_releases_verified'] and storage['both_native_and_pipeline_same_as_previous']
    assert storage['trace_source_sha256']==sha(e/'storage_audit2/executed_production_trace.py')
    assert storage['trace_source_sha256']==sha(a.archive/'source/tools/waveform_correction_v1/trace.py')
    assert all(c['relative_error']<2e-12 and c['qualified'] for c in storage['trace_controls'])
    assert all(c['no_correction_square_T'] for c in storage['cases'])
    assert sum(c['actual_pipeline_release_verified'] for c in storage['cases'])==20
    full,audit=report('full1'),report('full_audit1')
    assert full['result']=='waveform_correction_native_full_known_measured' and full['only_one_attempt']
    assert audit['result']=='independent_waveform_correction_native_full_verified'
    assert audit['producer_sha256']==sha(e/'full1/report.json')
    assert audit['auditor_sha256']==sha(e/'full_audit1/executed_audit.py')
    assert audit['solver_qualified'] and audit['fidelity_qualified'] and audit['all_phase_releases_verified']
    assert audit['stable_original_complete_normal']==v['full_corrected_normal']<=1e-11
    assert audit['gradient']==v['full_gradient']<2e-7 and audit['original_backward']==v['full_backward']<=1e-11
    assert audit['residual_gap_passed'] and audit['representer_gap_passed']
    assert audit['metrics']==v['full_metrics'] and audit['comparison_rows']==v['full_comparison_rows']
    assert len(audit['comparison_rows'])==17 and len(audit['original_correction_history'])==3
    assert audit['original_correction_history']==v['full_correction_history']
    assert audit['production_original_trace_relative_error']==v['full_production_trace_relative_error']<2e-11
    N,M,H=12289,49,288;n=2*M*H;k=min(N,n)
    assert 8*4096*N+8*N*n+8*(k+n)*k+8*k*k==v['full_base_four_array_bytes']==8368514064
    assert 8*N*n+8*n*k+16*k*k==v['full_correction_no_T_array_bytes']==7965828112
    preflight=full['resource_preflight']
    required=max(v['full_base_four_array_bytes'],v['full_correction_no_T_array_bytes'])+3*1024**3//2+3*1024**3
    assert preflight['required_available']==required and preflight['passed']
    assert min(preflight['available_physical_bytes'],preflight['available_commit_bytes'])>=required
    assert full['process_memory']['cumulative_peak_working_set_bytes']==v['full_actual_working_set_peak']
    assert full['process_memory']['cumulative_peak_private_commit_bytes']==v['full_actual_private_commit_peak']
    assert full['resources']['max_tracked_live_backing_bytes']==v['full_registered_backing_peak']
    assert not full['inverse_info']['separate_square_T_allocated']
    real=report('real_resources1')
    assert real['cases']==v['real_conditional_resource_cases'] and len(real['cases'])==12
    assert real['no_real_arrays_or_fit_allocated'] and not real['outer_corrected_phase_qualified']
    free=min(real['available_memory']['available_physical_bytes'],real['available_memory']['available_commit_bytes'])
    for c in real['cases']:
        N,M=c['frames'],c['nodes'];n=2*M*288;k=min(N,n)
        W,X,graph,T=8*4096*N,8*N*n,8*(k+n)*k,8*k*k
        right,inner=8*n*k,16*k*k
        assert c['individual_bytes']==dict(W_band=W,X=X,graph=graph,graph_T=T,inverse_right=right,inverse_inner=inner)
        for name,main in (('current_qualified_pipeline',max(W+X+graph+T,X+right+inner)),
                          ('hypothetical_no_base_T_and_early_X_release',max(W+X+graph,X+right,right+inner))):
            expected=main+3*1024**3//2+3*1024**3
            assert c[name]['main_arrays_only']==main and c[name]['required_available']==expected
            assert c[name]['available_gate_passed']==(free>=expected)
        assert not c['current_qualified_pipeline']['available_gate_passed']
        assert not c['hypothetical_path_implemented'] and c['conditional_NOT_peak_prediction']
        if c['scope']=='genuine_context':assert not c['hypothetical_no_base_T_and_early_X_release']['available_gate_passed']
    assert sha(e/'executed_package.py')==sha(a.archive/'source/tools/package_waveform_correction_storage_v1.py')
    assert not v['runtime_default_driver_owned_take_room_changed'] and v['no_real6_or_native48k_or_C_or_hearing_qualification']
    assert v['full_goal']=='active' and not v['outer_corrected_phase_qualified']
    result=dict(result='independent_waveform_correction_storage_archive_bindings_verified',
        source_bindings=sources,input_bindings=inputs,case_file_bindings=files,
        known_cases_exact=40,full_solver_and_fidelity=True,full_phase_releases=True,
        failure_retained=True,all17_fidelity_rows_retained=True,source_or_C_not_promoted=True,auditor_sha256=sha(Path(__file__)))
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n');print(result,flush=True)


if __name__=='__main__':main()
